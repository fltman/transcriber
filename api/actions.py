from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Action, ActionResult, ActionResultStatus, Meeting
from tasks.action_task import run_action_task

router = APIRouter(prefix="/api/actions", tags=["actions"])


class CreateActionRequest(BaseModel):
    name: str
    prompt: str


class UpdateActionRequest(BaseModel):
    name: str | None = None
    prompt: str | None = None


# --- Action CRUD ---

@router.get("")
def list_actions(db: Session = Depends(get_db)):
    actions = db.query(Action).order_by(Action.created_at).all()
    return [a.to_dict() for a in actions]


@router.post("")
def create_action(req: CreateActionRequest, db: Session = Depends(get_db)):
    action = Action(name=req.name, prompt=req.prompt)
    db.add(action)
    db.commit()
    db.refresh(action)
    return action.to_dict()


@router.put("/{action_id}")
def update_action(action_id: str, req: UpdateActionRequest, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(404, "Action not found")
    if req.name is not None:
        action.name = req.name
    if req.prompt is not None:
        action.prompt = req.prompt
    db.commit()
    db.refresh(action)
    return action.to_dict()


@router.delete("/{action_id}")
def delete_action(action_id: str, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(404, "Action not found")
    db.delete(action)
    db.commit()
    return {"ok": True}


# --- Execute action ---

@router.post("/{action_id}/run/{meeting_id}")
def run_action(action_id: str, meeting_id: str, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(404, "Action not found")

    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    result = ActionResult(
        action_id=action_id,
        meeting_id=meeting_id,
        status=ActionResultStatus.PENDING,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    task = run_action_task.delay(result.id)
    result.celery_task_id = task.id
    db.commit()

    return result.to_dict()


# --- Results ---

@router.get("/results/{meeting_id}")
def list_results(meeting_id: str, db: Session = Depends(get_db)):
    results = (
        db.query(ActionResult)
        .filter(ActionResult.meeting_id == meeting_id)
        .order_by(ActionResult.created_at.desc())
        .all()
    )
    # Enrich with action name
    action_ids = {r.action_id for r in results}
    actions = {a.id: a for a in db.query(Action).filter(Action.id.in_(action_ids)).all()}

    out = []
    for r in results:
        d = r.to_dict()
        a = actions.get(r.action_id)
        d["action_name"] = a.name if a else "Deleted action"
        out.append(d)
    return out


@router.delete("/results/{result_id}")
def delete_result(result_id: str, db: Session = Depends(get_db)):
    result = db.query(ActionResult).filter(ActionResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "Result not found")
    db.delete(result)
    db.commit()
    return {"ok": True}
