from unittest.mock import patch


def test_health_endpoint_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "cr-registration-ingest"


@patch("src.app.api.routes.registration.run_registration_ingestion")
def test_registration_ingest_endpoint_success(mock_run, client):
    mock_run.return_value = {
        "published": 5,
        "skipped": 0,
        "ingestion_timestamp": "2024-01-15T10:00:00+00:00",
    }

    response = client.post("/")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["payload"]["published"] == 5


@patch("src.app.api.routes.registration.run_registration_ingestion")
def test_registration_ingest_endpoint_handles_integration_error(mock_run, client):
    from src.app.integrations.randomuser.main import RandomUserError

    mock_run.side_effect = RandomUserError("api down")

    response = client.post("/")

    assert response.status_code == 502
    assert response.get_json()["error"] == "Integration Error"


@patch("src.app.api.routes.registration.run_registration_ingestion")
def test_registration_ingest_endpoint_handles_unexpected_error(mock_run, client):
    mock_run.side_effect = RuntimeError("boom")

    response = client.post("/")

    assert response.status_code == 500
    assert response.get_json()["error"] == "Internal Error"
