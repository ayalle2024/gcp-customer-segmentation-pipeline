"""Cliente para publicar eventos de registro en Pub/Sub."""

import json

from google.cloud import pubsub_v1

from src.app.core.config import PROJECT_ID, PUBSUB_TOPIC, SERVICE_NAME
from src.app.utils.logging import get_logger

logger = get_logger(SERVICE_NAME)

_publisher = None


class PubSubPublishError(RuntimeError):
    """Error publicando un evento en Pub/Sub."""


def _get_publisher() -> pubsub_v1.PublisherClient:
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def publish_registration_event(record: dict) -> None:
    try:
        publisher = _get_publisher()
        topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)
        message = json.dumps(record).encode("utf-8")
        future = publisher.publish(topic_path, message)
        future.result(timeout=15)
    except Exception as e:  # noqa: BLE001
        raise PubSubPublishError(f"Fallo publicando en {PUBSUB_TOPIC}: {e}") from e

    logger.info("Evento publicado en %s para customer_id=%s", PUBSUB_TOPIC, record.get("customer_id"))
