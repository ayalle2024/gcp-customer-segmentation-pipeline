CREATE TABLE IF NOT EXISTS `std_arl_all_randomuser.trx_customer_segment_decision` (
  customer_id   STRING NOT NULL OPTIONS (description = "Llave foránea hacia trx_customer_notification.customer_id."),
  decision      STRING NOT NULL OPTIONS (description = "Resultado de la regla de segmentación: 'marketing_only' o 'special_program'."),
  decided_at    TIMESTAMP NOT NULL OPTIONS (description = "Timestamp UTC en que se evaluó la decisión. Columna de particionamiento.")
)
PARTITION BY DATE(decided_at)
CLUSTER BY customer_id
OPTIONS (description = "Tabla transaccional: una decisión de segmento por cliente, evaluada por la Scheduled Query contra el dato sintético de enrollment.");
