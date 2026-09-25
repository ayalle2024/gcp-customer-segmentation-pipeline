from flask import Blueprint, jsonify

from src.app.core.config import LOG_SEPARATOR, SERVICE_NAME
from src.app.integrations.pubsub.main import PubSubPublishError
from src.app.integrations.randomuser.main import RandomUserError
from src.app.services.registration_service import run_registration_ingestion
from src.app.utils.common import safe_json_dumps
from src.app.utils.logging import get_logger

logger = get_logger(SERVICE_NAME)

registration_bp = Blueprint("registration", __name__)


@registration_bp.route("/", methods=["GET", "POST"])
@registration_bp.route("/registration-ingest", methods=["GET", "POST"])
def process_registration_ingestion():
    logger.info(LOG_SEPARATOR)
    logger.info("INICIO CR REGISTRATION INGEST")
    logger.info(LOG_SEPARATOR)

    try:
        result = run_registration_ingestion()

        response = {
            "status": "success",
            "service": SERVICE_NAME,
            "payload": result,
        }

        logger.info("Mensaje exacto de respuesta:")
        logger.info(safe_json_dumps(response))

        logger.info(LOG_SEPARATOR)
        logger.info("FIN CR REGISTRATION INGEST OK")
        logger.info(LOG_SEPARATOR)

        return jsonify(response), 200

    except (RandomUserError, PubSubPublishError) as e:
        logger.exception("Error de integración en Cloud Run")
        logger.info(LOG_SEPARATOR)
        logger.info("FIN CR REGISTRATION INGEST INTEGRATION_ERROR")
        logger.info(LOG_SEPARATOR)
        return jsonify({"error": "Integration Error", "detail": str(e)}), 502

    except Exception as e:
        logger.exception("Error en Cloud Run")
        logger.info(LOG_SEPARATOR)
        logger.info("FIN CR REGISTRATION INGEST ERROR")
        logger.info(LOG_SEPARATOR)
        return jsonify({"error": "Internal Error", "detail": str(e)}), 500
