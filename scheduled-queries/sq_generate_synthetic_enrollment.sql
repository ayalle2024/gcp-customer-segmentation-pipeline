-- sq_generate_synthetic_enrollment
-- Scheduled Query (on-demand). Corre antes de sq_evaluate_customer_segment
-- en cada ciclo. Genera datos sintéticos de enrollment para cualquier
-- cliente que todavía no tenga uno. Generados de forma determinística por
-- hash del customer_id (no son datos reales de negocio ni financieros).
-- Cada atributo usa su propio hash (sufijo distinto); con un hash compartido
-- todo cliente premium salía también inscrito (~30 % en vez de ~12 % special_program).

INSERT INTO `std_arl_all_randomuser.ori_mtr_program_enrollment`
  (customer_id, is_enrolled_program, account_tier, generated_at)
SELECT
  L.customer_id,
  MOD(ABS(FARM_FINGERPRINT(CONCAT(L.customer_id, '|enrollment'))), 10) < 4 AS is_enrolled_program,  -- ~40% enrolled
  IF(MOD(ABS(FARM_FINGERPRINT(CONCAT(L.customer_id, '|tier'))), 10) < 3, 'premium', 'basic') AS account_tier,  -- ~30% premium
  CURRENT_TIMESTAMP() AS generated_at
FROM `std_arl_all_randomuser.trx_customer_notification` L
LEFT JOIN `std_arl_all_randomuser.ori_mtr_program_enrollment` S
  ON L.customer_id = S.customer_id
WHERE S.customer_id IS NULL;
