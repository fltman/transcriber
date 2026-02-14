from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import settings

engine = create_engine(settings.database_url)
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
            except Exception:
                pass

        # Add new JobType enum values
        for val in ("POLISH_PASS", "FINALIZE_LIVE"):
            try:
                conn.execute(text(
                    f"ALTER TYPE jobtype ADD VALUE IF NOT EXISTS '{val}'"
                ))
            except Exception:
                pass

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
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        conn.commit()


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
