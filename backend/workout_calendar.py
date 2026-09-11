"""Calendar selection only for fully labelled, unambiguous weekly programs."""
import re
import unicodedata
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

# Browser offset (UTC minus local); legacy clients use Brasilia time.
browser_offset = ContextVar("forge_calendar_offset", default=180)
DAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
        "sexta": 4, "sabado": 5, "domingo": 6}

def calendar_today():
    return datetime.now(timezone(timedelta(minutes=-browser_offset.get()))).date()

def weekly_sessions(sessions):
    mapped = {}
    for session in sessions:
        label = unicodedata.normalize("NFD", str(session.get("label") or "").lower())
        label = "".join(c for c in label if not unicodedata.combining(c))
        match = re.match(r"^\s*(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?(?=\s|[·:—–-]|$)", label)
        if not match or DAYS[match[1]] in mapped:
            return None
        mapped[DAYS[match[1]]] = session
    return mapped or None

def calendar_selection(sessions, today=None, after_today=False):
    mapped = weekly_sessions(sessions)
    if mapped is None:
        return None
    today = today or calendar_today()
    weekday = today.weekday()
    current = mapped.get(weekday)
    offset = next(n for n in range(1 if after_today else 0, 8)
                  if (weekday + n) % 7 in mapped)
    return {"today": current, "next": mapped[(weekday + offset) % 7],
            "next_date": (today + timedelta(days=offset)).isoformat(),
            "weekdays": {str(s["day"]): w for w, s in mapped.items()}}
