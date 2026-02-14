import logging
import shutil
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import settings

log = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,  # verify connections before use
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Add new enum values BEFORE create_all (so the enum type exists with all values)
    with engine.connect() as conn:
        # Add new MeetingStatus enum values
        for val in ("RECORDING", "FINALIZING"):
            try:
                conn.execute(text(
                    f"ALTER TYPE meetingstatus ADD VALUE IF NOT EXISTS '{val}'"
                ))
            except Exception as e:
                log.debug(f"Enum value meetingstatus.{val}: {e}")

        # Add new JobType enum values
        for val in ("POLISH_PASS", "FINALIZE_LIVE", "REDIARIZE", "REIDENTIFY", "EXTRACT_INSIGHTS"):
            try:
                conn.execute(text(
                    f"ALTER TYPE jobtype ADD VALUE IF NOT EXISTS '{val}'"
                ))
            except Exception as e:
                log.debug(f"Enum value jobtype.{val}: {e}")

        conn.commit()

    Base.metadata.create_all(bind=engine)

    # Add new columns for live mode (safe to re-run)
    migrations = [
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'upload'",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS recording_status VARCHAR",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS polish_history JSON",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN DEFAULT FALSE",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS encryption_salt TEXT",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS encryption_verify TEXT",
        "ALTER TABLE action_results ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN DEFAULT FALSE",
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS vocabulary TEXT",
        # Full-text search index on segment text
        "CREATE INDEX IF NOT EXISTS ix_segments_text_search ON segments USING gin (to_tsvector('simple', text))",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception as e:
                log.debug(f"Migration skipped: {sql[:60]}... ({e})")
        conn.commit()


def recover_stale_jobs():
    """Mark any jobs stuck in RUNNING/PENDING as FAILED on startup.

    If the server restarts while a Celery task was running, the job
    status is stuck. This cleans them up so the user can retry.
    """
    from models.job import Job, JobStatus
    from models import Meeting, MeetingStatus

    db = SessionLocal()
    try:
        stale_jobs = db.query(Job).filter(
            Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
        ).all()
        for job in stale_jobs:
            job.status = JobStatus.FAILED
            job.error = "Task interrupted by server restart. Please retry."
            job.completed_at = datetime.utcnow()
            # Also reset the meeting status if it was stuck in PROCESSING/FINALIZING
            meeting = db.query(Meeting).filter(Meeting.id == job.meeting_id).first()
            if meeting and meeting.status in (MeetingStatus.PROCESSING, MeetingStatus.FINALIZING):
                meeting.status = MeetingStatus.FAILED
        if stale_jobs:
            db.commit()
            log.info(f"Recovered {len(stale_jobs)} stale job(s)")
    finally:
        db.close()


def cleanup_orphaned_storage():
    """Remove storage directories for meetings that no longer exist in the DB."""
    from config import get_storage_path
    from models import Meeting

    storage = get_storage_path()
    if not storage.exists():
        return

    db = SessionLocal()
    try:
        meeting_ids = {row[0] for row in db.query(Meeting.id).all()}
        removed = 0
        for d in storage.iterdir():
            if d.is_dir() and d.name not in meeting_ids:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        if removed:
            log.info(f"Cleaned up {removed} orphaned storage directory(s)")
    finally:
        db.close()


def seed_default_actions():
    """Create default actions if none exist."""
    from models.action import Action

    db = SessionLocal()
    try:
        if db.query(Action).count() > 0:
            return

        defaults = [
            Action(
                name="Sammanfattning",
                prompt=(
                    "Du ar en motesassistent. Skriv en tydlig och koncis sammanfattning av motet. "
                    "Inkludera: huvudamnen som diskuterades, viktiga beslut som fattades, "
                    "och eventuella olosta fragor. Skriv pa svenska."
                ),
                is_default=True,
            ),
            Action(
                name="Atgardslista",
                prompt=(
                    "Du ar en motesassistent. Skapa en strukturerad atgardslista fran motet. "
                    "For varje atgard, ange:\n"
                    "- Vad som ska goras\n"
                    "- Vem som ar ansvarig (om det framgar)\n"
                    "- Deadline (om det namns)\n\n"
                    "Formatera som en numrerad lista. Skriv pa svenska."
                ),
                is_default=True,
            ),
            Action(
                name="Avidentifierad version",
                prompt=(
                    "Du ar en integritetsspecialist. Skriv om transkriberingen sa att alla "
                    "personnamn ersatts med 'Person A', 'Person B', 'Person C' osv. "
                    "Ersatt aven organisationsnamn, platser och andra identifierande detaljer "
                    "med generiska termer. Behall innehallet intakt. Skriv pa svenska."
                ),
                is_default=True,
            ),
        ]

        for action in defaults:
            db.add(action)
        db.commit()
    finally:
        db.close()
