# Costos de servicios — `arl-dtpr-dev-cust-segmen`

Servicios de GCP que usa el proyecto Customer Segmentation, su capa gratuita y el gasto estimado.

> **Alcance de las cifras:** son una estimación a partir de lo desplegado y de las corridas de prueba (estado al 25/09/2026), no un dato de la consola de Facturación. El número exacto está en **Facturación → Informes**, filtrando por el proyecto `arl-dtpr-dev-cust-segmen`.

---

## Resumen

| Servicio | Uso en el proyecto | Free tier (mensual) | Costo estimado |
|---|---|---|---|
| BigQuery | 1 dataset (`std_arl_all_randomuser`), 3 tablas, decenas de filas por corrida | 10 GB de almacenamiento + 1 TB de consultas | **$0.00** |
| BigQuery Scheduled Queries | 2 queries on-demand, sin horario | Cuentan como consultas normales | **$0.00** |
| Firestore | Base `(default)`, colección `customer_prospects`, documentos de prueba | 1 GiB + 50 K lecturas y 20 K escrituras por día | **$0.00** |
| Cloud Run | 1 servicio propio (`cr-registration-ingest`) + 4 servicios internos de las Cloud Functions gen2 | 180 000 vCPU-s + 360 000 GiB-s + 2 M de requests | **$0.00** |
| Cloud Functions (gen2) | 4 funciones (3 por Pub/Sub, 1 por HTTP) | 2 M de invocaciones (compartidas con Cloud Run) | **$0.00** |
| Pub/Sub | 3 tópicos (`customer-registered`, `marketing-events`, `customer-segment-notification`) | 10 GB | **$0.00** |
| Cloud Workflows | 1 workflow (`orquestador-cust-segmen`), ejecución manual | Pasos internos y llamadas HTTP gratuitas cada mes (según el precio público de Workflows) | **$0.00** |
| Cloud Build | Un build por cada despliegue de Cloud Run o de una función | 2 500 minutos | **$0.00** |
| Artifact Registry | Imágenes de contenedor de los 5 servicios | 0.5 GB | **$0.00** |

**Total estimado: $0.00 USD.** Los 9 servicios trabajan dentro de su capa gratuita con el volumen de las pruebas.

---

## Detalle

### BigQuery y Scheduled Queries
- Dataset `std_arl_all_randomuser` con 3 tablas particionadas por fecha y agrupadas por `customer_id`: `trx_customer_notification`, `ori_mtr_program_enrollment` y `trx_customer_segment_decision`.
- Cada corrida del Workflow con `BATCH_SIZE=30` agrega 30 filas a cada tabla, un volumen muy por debajo de los límites.
- Las 2 Scheduled Queries (`sq_generate_synthetic_enrollment` y `sq_evaluate_customer_segment`) están en **on-demand**: no corren solas y se cobran como cualquier consulta, por bytes procesados. Con tablas de pocas filas, es una fracción mínima.
- Además, el Workflow ejecuta una consulta corta por intento en el paso que espera el enriquecimiento (una cada 10 s, hasta 30 intentos), también sobre una tabla de pocas filas.

### Firestore
- Base `(default)` en modo Native, región `us-central1`. La capa gratuita solo aplica a la base especial `(default)`, no a bases con nombre.
- `cf-enrich-and-notify` hace un upsert por cliente en `customer_prospects`: unas decenas de escrituras por corrida.

### Cloud Run y Cloud Functions gen2
- `cr-registration-ingest` es privado y solo lo invoca el Workflow.
- Cada Cloud Function gen2 corre sobre un servicio Cloud Run interno, por eso comparten la cuota gratuita de Cloud Run.
- Con `BATCH_SIZE=30`, una corrida produce del orden de 30 invocaciones por función y muy pocas de `cf-route-customer-decision` y `cf-notify-segment-consumer` (solo las decisiones `special_program`, cerca del 10 %).

### Pub/Sub
- Cada evento pesa menos de 1 KB. Una corrida publica del orden de 30 mensajes en `customer-registered` y otros tantos en `marketing-events`, más unos pocos en `customer-segment-notification`.

### Cloud Workflows
- Una ejecución manual por prueba. Cada una tiene un número de pasos que depende de cuánto tarde la espera de enriquecimiento (hasta 30 intentos por corrida).

### Cloud Build y Artifact Registry
- Cada despliegue de código dispara un build de 1–2 minutos con `sa-cloudbuild-segmen`. Las imágenes quedan en Artifact Registry (unas decenas de MB por servicio).
- Cloud Run usa Python 3.11 (`python:3.11-slim`) y las Cloud Functions usan Python 3.12.

---

## Cuándo empezaría a costar
Solo con un volumen muy superior al de una demo, por ejemplo miles de clientes por corrida y corridas automáticas frecuentes. Las Scheduled Queries siguen sin horario, así que nada corre por su cuenta.

## Cómo verificar el gasto real
1. Consola de GCP → **Facturación** → **Informes**.
2. Filtra por **Proyecto**: `arl-dtpr-dev-cust-segmen`.
3. Agrupa por **Servicio** para ver el desglose exacto.
