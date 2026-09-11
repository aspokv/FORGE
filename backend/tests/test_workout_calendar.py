from datetime import date, datetime, timezone
from unittest.mock import patch
import asyncio
import engine
from workout_calendar import calendar_selection, weekly_sessions, browser_offset, calendar_today

SESSIONS = [
    {"day": 1, "label": "Segunda · Upper A", "exercises": []},
    {"day": 2, "label": "Terça · Full Body A", "exercises": []},
    {"day": 3, "label": "Quarta · Upper B", "exercises": []},
    {"day": 4, "label": "Sexta · Upper C", "exercises": []},
    {"day": 5, "label": "Sábado · Full Body B", "exercises": []},
    {"day": 6, "label": "Domingo · Upper D", "exercises": []},
]

def test_friday_uses_weekday_not_session_number():
    result=calendar_selection(SESSIONS,date(2026,9,11))
    assert result["today"]["day"] == 4
    assert result["today"]["label"] == "Sexta · Upper C"
    assert result["weekdays"]["4"] == 4

def test_rest_and_sunday_wrap():
    rest=calendar_selection(SESSIONS,date(2026,9,10))
    assert rest["today"] is None
    assert rest["next"]["day"] == 4
    assert rest["next_date"] == "2026-09-11"
    sunday=calendar_selection(SESSIONS,date(2026,9,13),after_today=True)
    assert sunday["next"]["day"] == 1
    assert sunday["next_date"] == "2026-09-14"

def test_labels_are_explicit_and_unambiguous():
    assert weekly_sessions([{"day":1,"label":"Segunda-feira — Upper A"}])[0]["day"] == 1
    for labels in (["Push","Pull","Legs"],["Segunda · Upper","Full Body"],["Segunda · A","Segunda · B"]):
        assert weekly_sessions([{"day":i+1,"label":s} for i,s in enumerate(labels)]) is None

def test_saved_program_and_bootstrap_use_calendar_without_changing_profile():
    profile={"custom_program":{"sessions":SESSIONS},"current_session_day":1}
    with patch("workout_calendar.calendar_today",return_value=date(2026,9,11)):
        program=asyncio.run(engine.build_program_v2(profile))
    assert program["active_day"] == 4
    assert program["session"] == "Sexta · Upper C"
    assert profile["current_session_day"] == 1
    with patch("workout_calendar.calendar_today",return_value=date(2026,9,10)):
        rest=asyncio.run(engine.build_program_v2(profile))
    assert rest["active_day"] is None
    assert rest["rest_day"] is True

def test_unlabelled_ppl_keeps_pointer():
    assert engine._resolve_active_day([{"day":1,"label":"Push"},{"day":2,"label":"Pull"}],{"current_session_day":2}) == 2

def test_local_date_before_utc_midnight_boundary():
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2026,9,12,1,0,tzinfo=timezone.utc).astimezone(tz)
    token=browser_offset.set(180)
    try:
        with patch("workout_calendar.datetime",Clock):
            assert calendar_today() == date(2026,9,11)
    finally:
        browser_offset.reset(token)
