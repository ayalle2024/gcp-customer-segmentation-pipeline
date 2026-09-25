from unittest.mock import MagicMock, patch

import pytest

from src.utils import decode_pubsub_message, forward_to_segment_consumer


def test_decode_pubsub_message_decodes_base64_json(valid_pubsub_event, valid_segment_event):
    result = decode_pubsub_message(valid_pubsub_event)
    assert result == valid_segment_event


@patch("src.utils.requests.post")
def test_forward_to_segment_consumer_posts_payload(mock_post, valid_segment_event):
    mock_post.return_value = MagicMock(status_code=200)

    response = forward_to_segment_consumer(valid_segment_event)

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["json"] == valid_segment_event
    assert response.status_code == 200


@patch("src.utils.requests.post")
def test_forward_to_segment_consumer_raises_on_bad_status(mock_post, valid_segment_event):
    mock_post.return_value = MagicMock(status_code=500, text="internal error")

    with pytest.raises(RuntimeError):
        forward_to_segment_consumer(valid_segment_event)
