import os

# -------------------------------------------------------
# Configuración general del servicio
# -------------------------------------------------------

PROJECT_ID = os.environ.get("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
REGION = os.environ.get("REGION", "us-central1")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "cf-enrich-and-notify")

# -------------------------------------------------------
# BigQuery
# -------------------------------------------------------

BQ_DATASET = os.environ.get("BQ_DATASET", "std_arl_all_randomuser")
BQ_TABLE = os.environ.get("BQ_TABLE", "trx_customer_notification")

# -------------------------------------------------------
# Firestore
# -------------------------------------------------------

FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "customer_prospects")

# -------------------------------------------------------
# Pub/Sub (salida)
# -------------------------------------------------------

OUTPUT_PUBSUB_TOPIC = os.environ.get("OUTPUT_PUBSUB_TOPIC", "marketing-events")

# -------------------------------------------------------
# Logging
# -------------------------------------------------------

LOGGER_NAME = f"{SERVICE_NAME}-{PROJECT_ID}"
LOG_SEPARATOR = "======================================"
