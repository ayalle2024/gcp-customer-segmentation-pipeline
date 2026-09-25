import base64
import json
import os

import pytest

os.environ.setdefault("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
os.environ.setdefault("REGION", "us-central1")
os.environ.setdefault("SERVICE_NAME", "cf-notify-segment-consumer")
os.environ.setdefault("SEGMENT_CONSUMER_WEBHOOK_URL", "https://webhook.site/test-fake-url-2")
os.environ.setdefault("WEBHOOK_TIMEOUT_SECONDS", "10")


@pytest.fixture()
def valid_segment_event():
    return {"customer_id": "abc-123", "segment": "special_program"}


@pytest.fixture()
def valid_pubsub_event(valid_segment_event):
    encoded = base64.b64encode(json.dumps(valid_segment_event).encode("utf-8"))
    return {"data": encoded}
