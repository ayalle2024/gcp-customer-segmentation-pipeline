from src.config import LOG_SEPARATOR, LOGGER_NAME, PROJECT_ID, SERVICE_NAME
from src.gcp_logging import GCPLogger
from src.utils import (
    decode_pubsub_message,
    enrich_record,
    log_notification,
    publish_marketing_event,
    safe_json_dumps,
    upsert_prospect,
)

logger = GCPLogger.get_logger(LOGGER_NAME)


def main(event, context=None):
    """Entry point de la Cloud Function (trigger: Pub/Sub topic customer-registered)."""
    logger.info(LOG_SEPARATOR)
    logger.info("INICIO cf-enrich-and-notify")
    logger.info("Proyecto: %s", PROJECT_ID)
    logger.info("Servicio: %s", SERVICE_NAME)
    logger.info(LOG_SEPARATOR)

    try:
        record = decode_pubsub_message(event)
        logger.info("Evento recibido:")
        logger.info(safe_json_dumps(record))

        enriched = enrich_record(record)

        log_notification(enriched)
        upsert_prospect(enriched)
        publish_marketing_event(enriched)

        logger.info("Mensaje exacto procesado:")
        logger.info(safe_json_dumps(enriched))

        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-enrich-and-notify OK")
        logger.info(LOG_SEPARATOR)

        return enriched

    except Exception:
        logger.exception("Error en cf-enrich-and-notify")
        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-enrich-and-notify ERROR")
        logger.info(LOG_SEPARATOR)
        raise
