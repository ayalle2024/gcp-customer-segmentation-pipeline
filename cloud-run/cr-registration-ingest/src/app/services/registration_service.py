"""Lógica de negocio: orquesta fetch -> limpiar -> validar -> publicar."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.app.core.config import BATCH_SIZE, SERVICE_NAME
from src.app.integrations.pubsub.main import publish_registration_event
from src.app.integrations.randomuser.main import RandomUserError, fetch_random_users
from src.app.utils.logging import get_logger

logger = get_logger(SERVICE_NAME)


def clean_record(raw_user: dict, ingestion_ts: datetime) -> dict:
    """Aplana un perfil de RandomUser.me a un evento de registro de cliente."""
    name = raw_user.get("name") or {}
    location = raw_user.get("location") or {}

    return {
        "customer_id": str(uuid.uuid4()),
        "email": raw_user.get("email"),
        "first_name": name.get("first"),
        "last_name": name.get("last"),
        "country": location.get("country"),
        "registered_at": ingestion_ts.isoformat(),
    }


def is_valid_record(record: dict) -> bool:
    """Regla de calidad mínima antes de que un evento se publique."""
    if not record.get("email") or "@" not in (record.get("email") or ""):
        return False
    if not record.get("first_name") or not record.get("customer_id"):
        return False
    return True


def run_registration_ingestion() -> Dict[str, Any]:
    ingestion_ts = datetime.now(timezone.utc)

    try:
        raw_users = fetch_random_users(BATCH_SIZE)
    except RandomUserError as e:
        logger.error("Fallo consultando RandomUser.me: %s", e)
        raise

    published = 0
    skipped: List[str] = []

    for raw_user in raw_users:
        record = clean_record(raw_user, ingestion_ts)

        if not is_valid_record(record):
            skipped.append(record.get("customer_id", "unknown"))
            logger.warning("Registro inválido, se omite: %s", record.get("email"))
            continue

        publish_registration_event(record)
        published += 1

    return {
        "published": published,
        "skipped": len(skipped),
        "ingestion_timestamp": ingestion_ts.isoformat(),
    }
