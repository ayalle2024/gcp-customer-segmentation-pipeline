-- sq_evaluate_customer_segment
-- Scheduled Query (on-demand). Corre después de sq_generate_synthetic_enrollment
-- en cada ciclo. Evalúa la regla de segmentación: cliente inscrito en el
-- programa Y nivel de cuenta 'premium' -> 'special_program'; cualquier otro
-- caso -> 'marketing_only'.

MERGE `std_arl_all_randomuser.trx_customer_segment_decision` T
USING (
  SELECT
    L.customer_id,
    IF(S.is_enrolled_program AND S.account_tier = 'premium', 'special_program', 'marketing_only') AS decision,
    CURRENT_TIMESTAMP() AS decided_at
  FROM `std_arl_all_randomuser.trx_customer_notification` L
  JOIN `std_arl_all_randomuser.ori_mtr_program_enrollment` S
    ON L.customer_id = S.customer_id
) S
ON T.customer_id = S.customer_id
WHEN NOT MATCHED THEN
  INSERT (customer_id, decision, decided_at)
  VALUES (S.customer_id, S.decision, S.decided_at);
