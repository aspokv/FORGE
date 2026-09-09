from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from auth import get_current_user
from cardio import CardioLogIn, cardio_doc


router = APIRouter(prefix="/api/cardio", tags=["cardio"])


@router.post("")
async def log_cardio(payload: CardioLogIn, request: Request, user=Depends(get_current_user)):
    target = user["id"]
    doc = cardio_doc(payload, target, datetime.now(timezone.utc).isoformat())
    # A client token makes a retry idempotent instead of creating duplicate cardio logs.
    await request.app.state.db.cardio_logs.replace_one(
        {"profile_id": target, "client_token": doc["client_token"]},
        doc,
        upsert=True,
    )
    return {k: v for k, v in doc.items() if k != "user_id"}


@router.get("/recent")
async def recent_cardio(request: Request, limit: int = Query(default=20, ge=1, le=100), user=Depends(get_current_user)):
    rows = await request.app.state.db.cardio_logs.find(
        {"profile_id": user["id"], "completed": True}, {"_id": 0, "user_id": 0}
    ).sort("created_at", -1).to_list(length=limit)
    return {"items": rows}
