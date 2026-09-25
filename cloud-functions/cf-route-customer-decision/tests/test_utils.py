import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.utils import get_special_program_customers, publish_segment_notification


def test_get_special_program_customers_returns_ids_from_query_result():
    fake_row_1 = MagicMock(customer_id="abc-1")
    fake_row_2 = MagicMock(customer_id="abc-2")

    with patch("src.utils.bigquery_client") as mock_client:
        mock_client.query.return_value.result.return_value = [fake_row_1, fake_row_2]

        result = get_special_program_customers("2026-09-25T17:00:00Z")

    assert result == ["abc-1", "abc-2"]


def test_get_special_program_customers_filters_by_run_start_not_by_day():
    with patch("src.utils.bigquery_client") as mock_client:
        mock_client.query.return_value.result.return_value = []

        get_special_program_customers("2026-09-25T17:00:00.123456Z")

        query = mock_client.query.call_args.args[0]
        params = {p.name: p.value for p in mock_client.query.call_args.kwargs["job_config"].query_parameters}

    assert "CURRENT_DATE" not in query
    assert "decided_at >= @evaluation_started_at" in query
    assert params["evaluation_started_at"] == datetime(2026, 9, 25, 17, 0, 0, 123456, tzinfo=timezone.utc)


def test_publish_segment_notification_publishes_expected_payload():
    with patch("src.utils.publisher_client") as mock_publisher:
        mock_publisher.topic_path.return_value = "projects/p/topics/t"
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future

        publish_segment_notification("abc-1")

        mock_publisher.publish.assert_called_once()
        args, kwargs = mock_publisher.publish.call_args
        payload = json.loads(args[1].decode("utf-8"))
        assert payload == {"customer_id": "abc-1", "segment": "special_program"}
        mock_future.result.assert_called_once()
