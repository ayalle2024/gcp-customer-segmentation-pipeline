import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
os.environ.setdefault("REGION", "us-central1")
os.environ.setdefault("SERVICE_NAME", "cf-enrich-and-notify")
os.environ.setdefault("BQ_DATASET", "std_arl_all_randomuser")
os.environ.setdefault("BQ_TABLE", "trx_customer_notification")
os.environ.setdefault("FIRESTORE_COLLECTION", "customer_prospects")
os.environ.setdefault("OUTPUT_PUBSUB_TOPIC", "marketing-events")

# Los 3 clientes de GCP se instancian a nivel de módulo en src/utils.py — hay
# que mockearlos ANTES de importar ese módulo, para no intentar autenticarse
# de verdad contra GCP solo por correr los tests.
_bigquery_patcher = patch("google.cloud.bigquery.Client", return_value=MagicMock())
_firestore_patcher = patch("google.cloud.firestore.Client", return_value=MagicMock())
_pubsub_patcher = patch("google.cloud.pubsub_v1.PublisherClient", return_value=MagicMock())

_bigquery_patcher.start()
_firestore_patcher.start()
_pubsub_patcher.start()


def pytest_sessionfinish(session, exitstatus):
    _bigquery_patcher.stop()
    _firestore_patcher.stop()
    _pubsub_patcher.stop()


@pytest.fixture()
def valid_registration_event():
    return {
        "customer_id": "abc-123",
        "email": "maria.gomez@example.com",
        "first_name": "Maria",
        "last_name": "Gomez",
        "country": "Peru",
        "registered_at": "2024-01-15T10:00:00+00:00",
    }
