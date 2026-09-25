import base64
import json
import os

import pytest

os.environ.setdefault("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
os.environ.setdefault("REGION", "us-central1")
os.environ.setdefault("SERVICE_NAME", "cf-forward-to-marketing-platform")
os.environ.setdefault("MARKETING_WEBHOOK_URL", "https://webhook.site/test-fake-url")
os.environ.setdefault("WEBHOOK_TIMEOUT_SECONDS", "10")


@pytest.fixture()
def valid_marketing_event():
    return {
        "customer_id": "abc-123",
        "email": "maria.gomez@example.com",
        "prospect_status": "new",
        "enriched_at": "2026-09-17T18:00:00+00:00",
    }


@pytest.fixture()
def valid_pubsub_event(valid_marketing_event):
    encoded = base64.b64encode(json.dumps(valid_marketing_event).encode("utf-8"))
    return {"data": encoded}
