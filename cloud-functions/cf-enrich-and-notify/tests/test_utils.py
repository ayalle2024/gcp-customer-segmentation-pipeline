import base64
import json

from src.utils import decode_pubsub_message, enrich_record, safe_json_dumps


def test_decode_pubsub_message_decodes_base64_json(valid_registration_event):
    encoded = base64.b64encode(json.dumps(valid_registration_event).encode("utf-8"))
    event = {"data": encoded}

    result = decode_pubsub_message(event)

    assert result == valid_registration_event


def test_enrich_record_adds_metadata_without_losing_original_fields(valid_registration_event):
    enriched = enrich_record(valid_registration_event)

    assert enriched["customer_id"] == "abc-123"
    assert enriched["email"] == "maria.gomez@example.com"
    assert enriched["prospect_status"] == "new"
    assert "enriched_at" in enriched


def test_safe_json_dumps_handles_normal_dict():
    assert safe_json_dumps({"a": 1}) == '{"a":1}'


def test_safe_json_dumps_handles_non_serializable_value():
    class Weird:
        def __str__(self):
            return "weird-object"

    result = safe_json_dumps({"x": Weird()})
    assert "weird-object" in result
