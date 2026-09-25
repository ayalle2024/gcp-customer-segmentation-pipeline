import json
from typing import List

from google.cloud import bigquery, pubsub_v1

from src.config import (
    BQ_DATASET,
    BQ_TABLE,
    LOGGER_NAME,
    OUTPUT_PUBSUB_TOPIC,
    PROJECT_ID,
    SPECIAL_PROGRAM,
)
from src.gcp_logging import GCPLogger

logger = GCPLogger.get_logger(LOGGER_NAME)

bigquery_client = bigquery.Client(project=PROJECT_ID)
publisher_client = pubsub_v1.PublisherClient()


def get_special_program_customers(evaluation_started_at: str) -> List[str]:
    query = f"""
        SELECT customer_id
        FROM `{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE decision = @decision
          AND decided_at >= @evaluation_started_at
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("decision", "STRING", SPECIAL_PROGRAM),
            bigquery.ScalarQueryParameter("evaluation_started_at", "TIMESTAMP", evaluation_started_at),
        ]
    )
    rows = bigquery_client.query(query, job_config=job_config).result()
    return [row.customer_id for row in rows]


def publish_segment_notification(customer_id: str) -> None:
    topic_path = publisher_client.topic_path(PROJECT_ID, OUTPUT_PUBSUB_TOPIC)
    payload = {"customer_id": customer_id, "segment": SPECIAL_PROGRAM}
    future = publisher_client.publish(topic_path, json.dumps(payload).encode("utf-8"))
    future.result()
