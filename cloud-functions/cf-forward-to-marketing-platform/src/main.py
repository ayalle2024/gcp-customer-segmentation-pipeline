from src.config import LOG_SEPARATOR, LOGGER_NAME, PROJECT_ID, SERVICE_NAME
from src.gcp_logging import GCPLogger
from src.utils import decode_pubsub_message, forward_to_marketing_platform, safe_json_dumps

logger = GCPLogger.get_logger(LOGGER_NAME)


def main(event, context=None):
    logger.info(LOG_SEPARATOR)
    logger.info("INICIO cf-forward-to-marketing-platform")
    logger.info("Proyecto: %s", PROJECT_ID)
    logger.info("Servicio: %s", SERVICE_NAME)
    logger.info(LOG_SEPARATOR)
    try:
        payload = decode_pubsub_message(event)
        logger.info("Evento recibido:")
        logger.info(safe_json_dumps(payload))

        forward_to_marketing_platform(payload)
        logger.info("Plataforma de marketing notificada para customer_id=%s", payload.get("customer_id"))

        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-forward-to-marketing-platform OK")
        logger.info(LOG_SEPARATOR)
        return payload
    except Exception:
        logger.exception("Error en cf-forward-to-marketing-platform")
        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-forward-to-marketing-platform ERROR")
        logger.info(LOG_SEPARATOR)
        raise
