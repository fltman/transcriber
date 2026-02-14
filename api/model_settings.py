from fastapi import APIRouter
from pydantic import BaseModel

from model_config import get_model_config

router = APIRouter(prefix="/api/model-settings", tags=["model-settings"])


class UpdateAssignments(BaseModel):
    assignments: dict[str, str]


@router.get("")
def get_model_settings():
    """Return all presets and current task assignments."""
    mgr = get_model_config()
    mgr.reload()
    return {
        "presets": mgr.get_presets(),
        "assignments": mgr.get_assignments(),
    }


@router.put("")
def update_model_settings(body: UpdateAssignments):
    """Update task->preset assignments."""
    mgr = get_model_config()
    mgr.update_assignments(body.assignments)
    return {
        "presets": mgr.get_presets(),
        "assignments": mgr.get_assignments(),
    }
