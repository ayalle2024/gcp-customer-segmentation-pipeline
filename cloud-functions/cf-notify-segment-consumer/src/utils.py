import base64
import json
from typing import Any, Dict

import requests

from src.config import LOGGER_NAME, SEGMENT_CONSUMER_WEBHOOK_URL, WEBHOOK_TIMEOUT_SECONDS
from src.gcp_logging import GCPLogger

logger = GCPLogger.get_logger(LOGGER_NAME)


def safe_json_dumps(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return json.dumps(str(payload), ensure_ascii=False)


def decode_pubsub_message(event: Dict[str, Any]) -> Dict[str, Any]:
    raw_data = base64.b64decode(event["data"]).decode("utf-8")
    return json.loads(raw_data)


def forward_to_segment_consumer(payload: Dict[str, Any]) -> requests.Response:
    response = requests.post(SEGMENT_CONSUMER_WEBHOOK_URL, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)

    if response.status_code >= 300:
        logger.error("Webhook del consumidor de segmento respondió %s: %s", response.status_code, response.text)
        raise RuntimeError(f"Segment consumer webhook returned {response.status_code}")

    return response
