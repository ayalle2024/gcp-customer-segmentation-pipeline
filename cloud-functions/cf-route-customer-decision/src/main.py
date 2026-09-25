from src.config import LOG_SEPARATOR, LOGGER_NAME, PROJECT_ID, SERVICE_NAME
from src.gcp_logging import GCPLogger
from src.utils import get_special_program_customers, publish_segment_notification

logger = GCPLogger.get_logger(LOGGER_NAME)


def main(request):
    logger.info(LOG_SEPARATOR)
    logger.info("INICIO cf-route-customer-decision")
    logger.info("Proyecto: %s", PROJECT_ID)
    logger.info("Servicio: %s", SERVICE_NAME)
    logger.info(LOG_SEPARATOR)
    body = request.get_json(silent=True) or {}
    evaluation_started_at = body.get("evaluation_started_at")
    if not evaluation_started_at:
        logger.error("Falta evaluation_started_at en el cuerpo de la petición")
        return {"error": "evaluation_started_at es obligatorio"}, 400

    try:
        logger.info("Decisiones evaluadas desde: %s", evaluation_started_at)
        customer_ids = get_special_program_customers(evaluation_started_at)
        logger.info("Clientes special_program encontrados: %d", len(customer_ids))

        for customer_id in customer_ids:
            publish_segment_notification(customer_id)
            logger.info("Evento de segmento publicado para customer_id=%s", customer_id)

        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-route-customer-decision OK")
        logger.info(LOG_SEPARATOR)
        return {"routed": len(customer_ids)}, 200
    except Exception:
        logger.exception("Error en cf-route-customer-decision")
        logger.info(LOG_SEPARATOR)
        logger.info("FIN cf-route-customer-decision ERROR")
        logger.info(LOG_SEPARATOR)
        raise
