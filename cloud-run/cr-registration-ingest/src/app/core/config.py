import os

# -------------------------------------------------------
# Configuración general
# -------------------------------------------------------

PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT_ID", "arl-dtpr-dev-cust-segmen")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "cr-registration-ingest")

# -------------------------------------------------------
# RandomUser.me
# -------------------------------------------------------

RANDOM_USER_URL = os.environ.get("RANDOM_USER_URL", "https://randomuser.me/api/")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))

# -------------------------------------------------------
# Pub/Sub
# -------------------------------------------------------

PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", "customer-registered")

# -------------------------------------------------------
# Logging
# -------------------------------------------------------

LOG_SEPARATOR = "======================================"
