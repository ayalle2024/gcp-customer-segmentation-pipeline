import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
os.environ.setdefault("REGION", "us-central1")
os.environ.setdefault("SERVICE_NAME", "cf-route-customer-decision")
os.environ.setdefault("BQ_DATASET", "std_arl_all_randomuser")
os.environ.setdefault("BQ_TABLE", "trx_customer_segment_decision")
os.environ.setdefault("OUTPUT_PUBSUB_TOPIC", "customer-segment-notification")

_bigquery_patcher = patch("google.cloud.bigquery.Client", return_value=MagicMock())
_pubsub_patcher = patch("google.cloud.pubsub_v1.PublisherClient", return_value=MagicMock())

_bigquery_patcher.start()
_pubsub_patcher.start()


def pytest_sessionfinish(session, exitstatus):
    _bigquery_patcher.stop()
    _pubsub_patcher.stop()


@pytest.fixture()
def fake_request():
    request = MagicMock()
    request.get_json.return_value = {"evaluation_started_at": "2026-09-25T17:00:00Z"}
    return request
