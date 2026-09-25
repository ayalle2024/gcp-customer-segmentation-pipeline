CREATE SCHEMA IF NOT EXISTS `std_arl_all_randomuser`
  OPTIONS (
    location = 'US',
    description = "Capa estandarizada: registro de notificaciones de clientes, datos sintéticos de segmentación, y decisiones de segmento."
  );

CREATE TABLE IF NOT EXISTS `std_arl_all_randomuser.trx_customer_notification` (
  customer_id      STRING NOT NULL OPTIONS (description = "Identificador único del cliente (UUID generado en la ingesta)."),
  email            STRING NOT NULL OPTIONS (description = "Correo electrónico del cliente (simulado por RandomUser.me)."),
  first_name       STRING OPTIONS (description = "Nombre del cliente."),
  last_name        STRING OPTIONS (description = "Apellido del cliente."),
  country          STRING OPTIONS (description = "País del cliente, según la fuente."),
  registered_at    TIMESTAMP NOT NULL OPTIONS (description = "Timestamp UTC de registro simulado. Columna de particionamiento."),
  enriched_at      TIMESTAMP NOT NULL OPTIONS (description = "Timestamp UTC en que se enriqueció y notificó el registro."),
  prospect_status  STRING OPTIONS (description = "Estado del prospecto en el momento de la notificación (ej. 'new').")
)
PARTITION BY DATE(registered_at)
CLUSTER BY customer_id
OPTIONS (description = "Tabla transaccional: un registro por cada evento de registro de cliente enriquecido y forwardeado a la plataforma de marketing.");
