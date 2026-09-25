CREATE TABLE IF NOT EXISTS `std_arl_all_randomuser.ori_mtr_program_enrollment` (
  customer_id           STRING NOT NULL OPTIONS (description = "Llave foránea hacia trx_customer_notification.customer_id."),
  is_enrolled_program    BOOL NOT NULL OPTIONS (description = "Atributo sintético (~40% true), generado de forma determinística por hash del customer_id. Sin significado financiero ni real."),
  account_tier            STRING NOT NULL OPTIONS (description = "Nivel sintético de cuenta: 'basic' o 'premium' (~30% premium). Generado de forma determinística, no es un dato real."),
  generated_at             TIMESTAMP NOT NULL OPTIONS (description = "Timestamp UTC en que se generó este dato sintético.")
)
OPTIONS (description = "Dato sintético propio del negocio (no transversal): atributos de segmentación generados de forma reproducible por hash, sin datos financieros ni reales de ningún tipo.");
