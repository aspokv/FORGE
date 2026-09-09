"""Small, isolated cardio completion model for the FORGE workout finisher."""
from typing import Optional

from pydantic import BaseModel, Field


CARDIO_KINDS = {"moderate", "recovery", "free"}


class CardioLogIn(BaseModel):
    client_token: str = Field(..., min_length=8, max_length=80)
    kind: str = Field(default="moderate", max_length=24)
    modality: str = Field(..., min_length=2, max_length=40)
    minutes: int = Field(..., ge=1, le=120)
    rpe: int = Field(..., ge=1, le=10)
    session_day: Optional[int] = Field(default=None, ge=1, le=31)
    session_label: str = Field(default="", max_length=120)
    completed: bool = True


def cardio_doc(payload: CardioLogIn, profile_id: str, created_at: str) -> dict:
    kind = payload.kind if payload.kind in CARDIO_KINDS else "free"
    return {
        "profile_id": profile_id,
        "user_id": profile_id,
        "client_token": payload.client_token.strip(),
        "kind": kind,
        "modality": payload.modality.strip(),
        "minutes": payload.minutes,
        "rpe": payload.rpe,
        "session_day": payload.session_day,
        "session_label": payload.session_label.strip(),
        "completed": bool(payload.completed),
        "created_at": created_at,
    }
