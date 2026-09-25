from unittest.mock import Mock, patch

import pytest
import requests

from src.app.integrations.randomuser.main import RandomUserError, fetch_random_users


@patch("src.app.integrations.randomuser.main.requests.get")
def test_fetch_random_users_returns_results_on_success(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"results": [{"email": "a@b.com"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = fetch_random_users(1)

    assert result == [{"email": "a@b.com"}]


@patch("src.app.integrations.randomuser.main.requests.get")
def test_fetch_random_users_raises_error_on_network_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("no network")

    with pytest.raises(RandomUserError):
        fetch_random_users(1)


@patch("src.app.integrations.randomuser.main.requests.get")
def test_fetch_random_users_raises_error_on_invalid_json(mock_get):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("not json")
    mock_get.return_value = mock_response

    with pytest.raises(RandomUserError):
        fetch_random_users(1)
