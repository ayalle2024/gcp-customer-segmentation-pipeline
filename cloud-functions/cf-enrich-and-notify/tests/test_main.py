import base64
import json
from unittest.mock import patch

from src.main import main


def _build_event(record: dict) -> dict:
    encoded = base64.b64encode(json.dumps(record).encode("utf-8"))
    return {"data": encoded}


@patch("src.main.publish_marketing_event")
@patch("src.main.upsert_prospect")
@patch("src.main.log_notification")
def test_main_processes_event_successfully(mock_log, mock_upsert, mock_publish, valid_registration_event):
    event = _build_event(valid_registration_event)

    result = main(event)

    assert result["customer_id"] == "abc-123"
    assert result["prospect_status"] == "new"
    mock_log.assert_called_once()
    mock_upsert.assert_called_once()
    mock_publish.assert_called_once()


@patch("src.main.log_notification", side_effect=RuntimeError("bigquery down"))
def test_main_raises_when_bigquery_insert_fails(mock_log, valid_registration_event):
    event = _build_event(valid_registration_event)

    try:
        main(event)
        assert False, "se esperaba que main() propagara la excepción"
    except RuntimeError as e:
        assert "bigquery down" in str(e)
