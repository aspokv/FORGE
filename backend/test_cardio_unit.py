import pytest
from pydantic import ValidationError

from cardio import CardioLogIn, cardio_doc


def test_cardio_doc_is_profile_scoped_and_normalized():
    payload = CardioLogIn(
        client_token="cardio-12345678",
        kind="recovery",
        modality=" Bike ",
        minutes=10,
        rpe=3,
        session_label=" Legs ",
    )
    doc = cardio_doc(payload, "athlete-1", "2026-09-09T10:00:00+00:00")
    assert doc["profile_id"] == "athlete-1"
    assert doc["modality"] == "Bike"
    assert doc["session_label"] == "Legs"
    assert doc["minutes"] == 10
    assert doc["rpe"] == 3


def test_cardio_rejects_invalid_duration_and_rpe():
    with pytest.raises(ValidationError):
        CardioLogIn(client_token="cardio-12345678", modality="Bike", minutes=0, rpe=4)
    with pytest.raises(ValidationError):
        CardioLogIn(client_token="cardio-12345678", modality="Bike", minutes=15, rpe=11)
