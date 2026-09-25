import os

PROJECT_ID = os.environ.get("PROJECT_ID", "arl-dtpr-dev-cust-segmen")
REGION = os.environ.get("REGION", "us-central1")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "cf-route-customer-decision")

BQ_DATASET = os.environ.get("BQ_DATASET", "std_arl_all_randomuser")
BQ_TABLE = os.environ.get("BQ_TABLE", "trx_customer_segment_decision")

OUTPUT_PUBSUB_TOPIC = os.environ.get("OUTPUT_PUBSUB_TOPIC", "customer-segment-notification")

SPECIAL_PROGRAM = "special_program"
MARKETING_ONLY = "marketing_only"

LOGGER_NAME = f"{SERVICE_NAME}-{PROJECT_ID}"
LOG_SEPARATOR = "======================================"
