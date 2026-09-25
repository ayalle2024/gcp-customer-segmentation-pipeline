# Cuentas de servicio — `arl-dtpr-dev-cust-segmen`

Registro de todas las cuentas de servicio (service accounts) que existen y se
usan activamente en este proyecto, para qué sirve cada una, y qué permisos
tiene exactamente.

> `<PROJECT_NUMBER>` es el número del proyecto; se obtiene con
> `gcloud projects describe arl-dtpr-dev-cust-segmen --format="value(projectNumber)"`.

---

## 1. `sa-cloudrun-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`

**Nombre:** `sa-cloudrun-segmen`

**Convención de nombre:** `sa-<tipo-de-componente>-<último-segmento-del-project-id>`
(`segmen`, último segmento de `arl-dtpr-dev-cust-segmen`).

**Para qué se usa:** es la identidad de ejecución **compartida por todas las
Cloud Run** de este proyecto (hoy solo `cr-registration-ingest`, pero si se
agregan más Cloud Run en el futuro, usan la misma cuenta — un service
account por *tipo* de componente, no por instancia).

**Permisos que tiene:**
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/pubsub.publisher` | Tópico `customer-registered` | `cr-registration-ingest` publica un evento por cada registro simulado de RandomUser.me |

---

## 2. `sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`

**Nombre:** `sa-cloudfunction-segmen`

**Para qué se usa:** es la identidad de ejecución **compartida por las 4
Cloud Functions** de este proyecto:
- `cf-enrich-and-notify`
- `cf-forward-to-marketing-platform`
- `cf-route-customer-decision`
- `cf-notify-segment-consumer`

También es la identidad que usan los **triggers de Eventarc/Pub/Sub** de las
3 funciones disparadas por Pub/Sub (el campo `eventTrigger.serviceAccountEmail`
de cada función apunta a esta misma cuenta).

**Permisos que tiene:**
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/bigquery.dataEditor` | Solo el dataset `std_arl_all_randomuser` | Insertar en `trx_customer_notification` (`cf-enrich-and-notify`) y leer `trx_customer_segment_decision` (`cf-route-customer-decision`). Se otorga con `GRANT ... ON SCHEMA` (DCL de BigQuery); se retiró el permiso que tenía a nivel de proyecto |
| `roles/bigquery.jobUser` | Todo el proyecto | Ejecutar los jobs de consulta (`SELECT`) que corre `cf-route-customer-decision` |
| `roles/datastore.user` | Todo el proyecto (Firestore Native usa roles con prefijo `datastore` por herencia histórica de Datastore) | `cf-enrich-and-notify` hace upsert en la colección `customer_prospects` |
| `roles/pubsub.publisher` | Tópicos `marketing-events` y `customer-segment-notification` | `cf-enrich-and-notify` republica en `marketing-events`; `cf-route-customer-decision` publica en `customer-segment-notification` |
| `roles/logging.logWriter` | Todo el proyecto | Logs estructurados de las 4 funciones |
| `roles/run.invoker` | Los 3 servicios Cloud Run subyacentes de las funciones con trigger de Pub/Sub (`cf-enrich-and-notify`, `cf-forward-to-marketing-platform`, `cf-notify-segment-consumer`) | Necesario porque toda Cloud Function gen2 corre sobre un servicio Cloud Run interno — sin este permiso, el trigger de Eventarc/Pub/Sub recibe `401 The request was not authenticated`. `cf-route-customer-decision` no lo necesita: solo la invoca el Workflow (ver sección 6) |
| `roles/iam.serviceAccountTokenCreator` (otorgado *sobre* esta cuenta, no *por* ella) | — | El agente de servicio de Pub/Sub (`service-<PROJECT_NUMBER>@gcp-sa-pubsub.iam.gserviceaccount.com`) necesita este rol sobre `sa-cloudfunction-segmen` para poder generar tokens OIDC en su nombre al invocar las funciones con trigger de Pub/Sub |

**Nota sobre `run.invoker`:** cada vez que se crea una Cloud Function gen2
nueva, hay que agregar explícitamente este permiso apenas termina el
`gcloud functions deploy` — no viene incluido, y sin él el trigger falla con
reintentos silenciosos (visibles en logs como `401` con backoff exponencial).

---

## 3. `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`

**Nombre:** Default compute service account (cuenta autogenerada por GCP)

**Estado actual (tras el hardening de IAM): sin uso y sin permisos de proyecto.**
- **Cloud Build** usa `sa-cloudbuild-segmen` (`--build-service-account` en cada
  `gcloud run deploy` / `gcloud functions deploy`).
- Las 2 **BigQuery Scheduled Queries** corren como `sa-scheduledquery-segmen`.
  Antes, `sq_generate_synthetic_enrollment` usaba esta cuenta y
  `sq_evaluate_customer_segment` no tenía cuenta de servicio (corría con las
  credenciales del usuario).

**Permisos que tiene:** ninguno de proyecto. Se le retiró `roles/editor`
(heredado automáticamente por GCP al crearla), y se verificó con el Workflow y
con los redespliegues del Cloud Run y de una Cloud Function.

> La cuenta default de App Engine
> (`arl-dtpr-dev-cust-segmen@appspot.gserviceaccount.com`) también tenía
> `roles/editor` y ningún componente la usa; se le retiró y se verificó con el
> Workflow y con los logs de `cf-enrich-and-notify`.

---

## 4. `sa-scheduledquery-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`

**Para qué se usa:** identidad de ejecución de las 2 Scheduled Queries
(`sq_generate_synthetic_enrollment`, `sq_evaluate_customer_segment`), una sola
cuenta por *tipo* de componente. Se configura en la consola, en cada query:
Edit → Schedule → Update scheduled query → Service account.

**Permisos que tiene:**
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/bigquery.jobUser` | Proyecto | Poder ejecutar las queries |
| `roles/bigquery.dataEditor` | Dataset `std_arl_all_randomuser` | Ambas queries leen y escriben solo ese dataset |

**Cuidado al guardar:** ese panel también trae **Schedule options**. Antes de
**Save**, dejar **Repeat frequency = On-demand**; si no, el panel puede activar
un horario cada hora.

**Verificación:** el `user_email` del job `scheduled_query_<id>` en
`INFORMATION_SCHEMA.JOBS_BY_PROJECT` es esta cuenta.

---

## 5. `sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`

**Para qué se usa:** identidad de **Cloud Build** en los despliegues de la
Cloud Run y de las Cloud Functions, indicada con `--build-service-account`.

**Permisos que tiene:** `roles/run.builder` (proyecto). Verificado también para
builds de Cloud Functions gen2.

---

## 6. `sa-workflow-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`

**Para qué se usa:** identidad del Workflow `orquestador-cust-segmen`.

**Permisos que tiene:**
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/run.invoker` | `cr-registration-ingest` y `cf-route-customer-decision` | Llamar a ambos servicios con un token OIDC |
| Rol personalizado `custSegmenTransferRunner` (solo `bigquery.transfers.get` y `bigquery.transfers.update`) | Proyecto | Disparar y consultar las 2 Scheduled Queries |
| `roles/bigquery.jobUser` | Proyecto | Ejecutar la consulta que cuenta los clientes ya enriquecidos (paso de espera del Workflow) |
| `roles/bigquery.dataViewer` | Dataset `std_arl_all_randomuser` | Esa consulta lee `trx_customer_notification` |
| `roles/logging.logWriter` | Proyecto | Logs de ejecución del Workflow |

---

## Resumen

| Cuenta | Tipo | Usada por | Permiso principal |
|---|---|---|---|
| `sa-cloudrun-segmen` | Creada a propósito | `cr-registration-ingest` | `pubsub.publisher` en `customer-registered` |
| `sa-cloudfunction-segmen` | Creada a propósito | Las 4 Cloud Functions + sus triggers de Pub/Sub | `bigquery.dataEditor` (solo `std_arl_all_randomuser`), `bigquery.jobUser`, `datastore.user`, `pubsub.publisher`, `logging.logWriter`, `run.invoker` (x3 servicios con trigger de Pub/Sub) |
| `sa-scheduledquery-segmen` | Creada a propósito (hardening) | Las 2 Scheduled Queries | `bigquery.jobUser` + `dataEditor` en `std_arl_all_randomuser` |
| `sa-cloudbuild-segmen` | Creada a propósito (hardening) | Cloud Build (deploys) | `run.builder` |
| `sa-workflow-segmen` | Creada a propósito | Workflow `orquestador-cust-segmen` | `run.invoker` (x2) + `custSegmenTransferRunner` + `bigquery.jobUser` + `dataViewer` en `std_arl_all_randomuser` + `logging.logWriter` |
| `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com` | Automática (default) | **Ningún componente** | Sin `roles/editor` (retirado) |

## Notas de diseño

- **Un service account por tipo de componente, no por instancia**: las 4
  Cloud Functions comparten `sa-cloudfunction-segmen` en vez de tener una
  cuenta cada una — decisión explícita para no crear cuentas de más.
- **Firestore requirió recrear la base de datos**: la consola de BigQuery/
  Firestore, al escribir `default` como Database ID (sin poder teclear los
  paréntesis), crea una base **con nombre** llamada `default`
  (`projects/.../databases/default`), distinta de la base especial
  `(default)` (`projects/.../databases/(default)`) que usa el cliente de
  Python sin configuración adicional — y que además es la única elegible
  para la cuota gratuita de Firestore. Se resolvió borrando la base con
  nombre y creándola por `gcloud firestore databases create` (sin
  `--database`), que sí genera la especial `(default)`.
