import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict

from google.cloud import bigquery, firestore, pubsub_v1

from src.config import (
    BQ_DATASET,
    BQ_TABLE,
    FIRESTORE_COLLECTION,
    LOGGER_NAME,
    OUTPUT_PUBSUB_TOPIC,
    PROJECT_ID,
)
from src.gcp_logging import GCPLogger

logger = GCPLogger.get_logger(LOGGER_NAME)

bigquery_client = bigquery.Client(project=PROJECT_ID)
firestore_client = firestore.Client(project=PROJECT_ID)
publisher_client = pubsub_v1.PublisherClient()


# -------------------------------------------------------
# Helpers generales
# -------------------------------------------------------

def safe_json_dumps(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
        default=str,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------------------------------------------------
# Decodificación del evento de Pub/Sub
# -------------------------------------------------------

def decode_pubsub_message(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pub/Sub entrega el payload codificado en base64 dentro de event['data']."""
    raw_data = base64.b64decode(event["data"]).decode("utf-8")
    return json.loads(raw_data)


# -------------------------------------------------------
# Enriquecimiento
# -------------------------------------------------------

def enrich_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Agrega metadata de procesamiento al evento crudo de registro."""
    enriched = dict(record)
    enriched["enriched_at"] = utc_now_iso()
    enriched["prospect_status"] = "new"
    return enriched


# -------------------------------------------------------
# BigQuery
# -------------------------------------------------------

def log_notification(enriched: Dict[str, Any]) -> None:
    table_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

    errors = bigquery_client.insert_rows_json(table_id, [enriched])
    if errors:
        raise RuntimeError(f"Errores insertando en {table_id}: {errors}")

    logger.info("Notificación registrada en %s para customer_id=%s", table_id, enriched.get("customer_id"))


# -------------------------------------------------------
# Firestore
# -------------------------------------------------------

def upsert_prospect(enriched: Dict[str, Any]) -> None:
    firestore_client.collection(FIRESTORE_COLLECTION).document(enriched["customer_id"]).set(enriched, merge=True)
    logger.info("Prospecto actualizado en Firestore: %s", enriched.get("customer_id"))


# -------------------------------------------------------
# Pub/Sub (salida)
# -------------------------------------------------------

def publish_marketing_event(enriched: Dict[str, Any]) -> None:
    payload = {
        "customer_id": enriched["customer_id"],
        "email": enriched["email"],
        "first_name": enriched["first_name"],
        "event": "welcome_email",
    }

    topic_path = publisher_client.topic_path(PROJECT_ID, OUTPUT_PUBSUB_TOPIC)
    future = publisher_client.publish(topic_path, safe_json_dumps(payload).encode("utf-8"))
    message_id = future.result(timeout=15)

    logger.info("Evento de marketing publicado (message_id=%s) para customer_id=%s", message_id, enriched.get("customer_id"))
