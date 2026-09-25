from unittest.mock import patch

from src.main import main


@patch("src.main.publish_segment_notification")
@patch("src.main.get_special_program_customers", return_value=["abc-1", "abc-2"])
def test_main_routes_all_special_program_customers(mock_get, mock_publish, fake_request):
    body, status = main(fake_request)

    assert status == 200
    assert body == {"routed": 2}
    assert mock_publish.call_count == 2


@patch("src.main.get_special_program_customers", return_value=[])
def test_main_returns_zero_when_no_customers(mock_get, fake_request):
    body, status = main(fake_request)

    assert status == 200
    assert body == {"routed": 0}


@patch("src.main.get_special_program_customers", side_effect=RuntimeError("bigquery down"))
def test_main_raises_on_query_failure(mock_get, fake_request):
    import pytest

    with pytest.raises(RuntimeError, match="bigquery down"):
        main(fake_request)


@patch("src.main.get_special_program_customers")
def test_main_passes_run_start_to_query(mock_get, fake_request):
    mock_get.return_value = []

    main(fake_request)

    mock_get.assert_called_once_with("2026-09-25T17:00:00Z")


@patch("src.main.get_special_program_customers")
def test_main_returns_400_without_evaluation_started_at(mock_get, fake_request):
    fake_request.get_json.return_value = {}

    body, status = main(fake_request)

    assert status == 400
    mock_get.assert_not_called()
