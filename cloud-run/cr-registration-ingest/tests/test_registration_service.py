from datetime import datetime, timezone

from src.app.services.registration_service import clean_record, is_valid_record

SAMPLE_RAW_USER = {
    "name": {"first": "Maria", "last": "Gomez"},
    "email": "maria.gomez@example.com",
    "location": {"country": "Peru"},
}


def test_clean_record_flattens_randomuser_payload():
    ts = datetime(2024, 1, 15, tzinfo=timezone.utc)

    record = clean_record(SAMPLE_RAW_USER, ts)

    assert record["email"] == "maria.gomez@example.com"
    assert record["first_name"] == "Maria"
    assert record["last_name"] == "Gomez"
    assert record["country"] == "Peru"
    assert record["customer_id"]
    assert record["registered_at"] == ts.isoformat()


def test_valid_record_passes():
    record = {"customer_id": "abc-123", "email": "a@b.com", "first_name": "Maria"}
    assert is_valid_record(record) is True


def test_missing_email_is_rejected():
    record = {"customer_id": "abc-123", "email": None, "first_name": "Maria"}
    assert is_valid_record(record) is False


def test_malformed_email_is_rejected():
    record = {"customer_id": "abc-123", "email": "not-an-email", "first_name": "Maria"}
    assert is_valid_record(record) is False


def test_missing_first_name_is_rejected():
    record = {"customer_id": "abc-123", "email": "a@b.com", "first_name": None}
    assert is_valid_record(record) is False
