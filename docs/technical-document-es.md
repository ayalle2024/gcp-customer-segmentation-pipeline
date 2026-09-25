# Documento Técnico de Despliegue
## Customer Segmentation (`arl-dtpr-dev-cust-segmen`)

**Autor:** Alvaro Yalle
**Organización:** Arla & Asociados
**Última actualización:** 25/09/2026 (correcciones tras la revisión, sección 18)
**Versión:** 2 (ver sección 16, evolución frente a la versión 1, y sección 18, correcciones tras la revisión)

---

## 1. Resumen del proyecto

| Campo | Valor |
|---|---|
| Project ID | `arl-dtpr-dev-cust-segmen` |
| Número de proyecto | `<PROJECT_NUMBER>` (`gcloud projects describe arl-dtpr-dev-cust-segmen --format="value(projectNumber)"`) |
| Región | `us-central1` (BigQuery y Data Transfer en `us`) |
| Taxonomía | `<bu>-<capability>-<env>-<domain>` → `arl` (Arla & Asociados) · `dtpr` (Data Products) · `dev` · `cust-segmen` (Customer Segmentation) |
| Patrón que demuestra | Arquitectura orientada a eventos (Pub/Sub) con enrutamiento por reglas de negocio y notificación a sistemas externos |
| Fuente de datos | API pública RandomUser.me (`https://randomuser.me/api/`) |
| Datos sintéticos | Inscripción a programa y nivel de cuenta, generados por hash dentro de BigQuery (sin datos reales ni financieros) |
| Sistemas externos simulados | 2 webhooks de [webhook.site](https://webhook.site) |
| Costo | $0.00 — dentro del free tier permanente de GCP |

### 1.1. Qué hace el proyecto, en una frase
Simula el registro de clientes, los enriquece y los guarda (BigQuery + Firestore), los notifica a una plataforma de marketing, decide con una regla de negocio si cada cliente pertenece al segmento `special_program` o `marketing_only`, y notifica a un sistema externo solo los clientes del programa especial. Un Cloud Workflow encadena todo el proceso en una sola ejecución.

### 1.2. Regla de segmentación
```
is_enrolled_program = true  AND  account_tier = 'premium'   →  special_program
cualquier otro caso                                          →  marketing_only
```
Probabilidades sintéticas: ~40 % inscritos, ~30 % premium → **~12 % de los clientes** caen en `special_program`. Para que las dos probabilidades sean realmente independientes, cada atributo se calcula con su propio hash (sección 11.1). Corrida de prueba del 25/09/2026 con 30 clientes: 11 inscritos, 7 premium y 3 en `special_program`.

### 1.3. Inventario de componentes (15 en el flujo orquestado)

| # | Tipo | Nombre | Rol |
|---|---|---|---|
| 1 | Cloud Workflow | `orquestador-cust-segmen` | Orquesta todo el pipeline |
| 2 | Cloud Run | `cr-registration-ingest` | Consulta RandomUser.me y publica eventos |
| 3 | Pub/Sub | `customer-registered` | Bus de registros de clientes |
| 4 | Cloud Function | `cf-enrich-and-notify` | Enriquece, guarda y republica |
| 5 | BigQuery (tabla) | `trx_customer_notification` | Histórico de clientes enriquecidos |
| 6 | Firestore | `customer_prospects` | Estado actual de cada prospecto |
| 7 | Pub/Sub | `marketing-events` | Bus de eventos de marketing |
| 8 | Cloud Function | `cf-forward-to-marketing-platform` | Notifica a la plataforma de marketing |
| 9 | BigQuery Scheduled Query | `sq_generate_synthetic_enrollment` | Genera inscripción sintética |
| 10 | BigQuery (tabla) | `ori_mtr_program_enrollment` | Datos sintéticos de inscripción |
| 11 | BigQuery Scheduled Query | `sq_evaluate_customer_segment` | Evalúa la regla de segmentación |
| 12 | BigQuery (tabla) | `trx_customer_segment_decision` | Decisión de segmento por cliente |
| 13 | Cloud Function | `cf-route-customer-decision` | Enruta los clientes `special_program` |
| 14 | Pub/Sub | `customer-segment-notification` | Bus de notificaciones de segmento |
| 15 | Cloud Function | `cf-notify-segment-consumer` | Notifica al consumidor del programa especial |

---

## 2. Arquitectura

```
Workflow: orquestador-cust-segmen  (botón Execute)
   │
   ├─► Paso 1: POST OIDC ─► Cloud Run: cr-registration-ingest ──► RandomUser.me
   │                              │
   │                              ▼
   │                    Pub/Sub: customer-registered
   │                              │
   │                              ▼
   │                    cf-enrich-and-notify ──┬─► BigQuery: trx_customer_notification
   │                                           ├─► Firestore: customer_prospects
   │                                           └─► Pub/Sub: marketing-events
   │                                                        │
   │                                                        ▼
   │                                      cf-forward-to-marketing-platform ─► Webhook #1
   │
   ├─► Paso 2: espera (polling, con tiempo máximo) a que los clientes publicados
   │           ya estén en trx_customer_notification
   │
   ├─► Paso 3: Scheduled Query sq_generate_synthetic_enrollment ─► ori_mtr_program_enrollment
   │           (dispara y espera con polling)
   │
   ├─► Paso 4: Scheduled Query sq_evaluate_customer_segment ─► trx_customer_segment_decision
   │           (dispara y espera con polling)
   │
   └─► Paso 5: POST OIDC (con evaluation_started_at) ─► cf-route-customer-decision (HTTP)
                                  │
                                  ▼
                        Pub/Sub: customer-segment-notification
                                  │
                                  ▼
                        cf-notify-segment-consumer ─► Webhook #2
```

### 2.1. Dos tramos automáticos disparados en cascada
- **Primer tramo** (lo dispara el paso 1): `customer-registered → cf-enrich-and-notify → marketing-events → cf-forward-to-marketing-platform → webhook #1`. Es asíncrono: el Workflow espera la respuesta de Cloud Run y, en el paso 2, comprueba en BigQuery que todos los clientes publicados llegaron a `trx_customer_notification` antes de seguir.
- **Segundo tramo** (lo dispara el paso 5): `customer-segment-notification → cf-notify-segment-consumer → webhook #2`.

### 2.2. Orden de ejecución
1. Workflow → 2. Cloud Run → 3. `customer-registered` → 4. `cf-enrich-and-notify` → 5. `trx_customer_notification` → 6. `customer_prospects` → 7. `marketing-events` → 8. `cf-forward-to-marketing-platform` → (espera de enriquecimiento en el Workflow) → 9. `sq_generate_synthetic_enrollment` → 10. `ori_mtr_program_enrollment` → 11. `sq_evaluate_customer_segment` → 12. `trx_customer_segment_decision` → 13. `cf-route-customer-decision` → 14. `customer-segment-notification` → 15. `cf-notify-segment-consumer`.

---

## 3. Prerrequisitos

### 3.1. Cuenta y herramientas
```bash
gcloud auth login
gcloud config set project arl-dtpr-dev-cust-segmen
```
Python 3.11+ para las pruebas locales (el Cloud Run usa `python:3.11-slim`; las Cloud Functions, el runtime `python312`); `uv` opcional para generar `requirements.txt`.

### 3.2. Habilitar las APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  bigquerydatatransfer.googleapis.com \
  firestore.googleapis.com \
  workflows.googleapis.com \
  iam.googleapis.com \
  --project=arl-dtpr-dev-cust-segmen
```
Si el primer deploy de Workflow falla con `Workflows service agent does not exist (Code: 9)`:
```bash
gcloud beta services identity create --service=workflows.googleapis.com --project=arl-dtpr-dev-cust-segmen
```

### 3.3. Cuenta de Cloud Build
Todos los despliegues usan `sa-cloudbuild-segmen` con `--build-service-account` (sección 5.4.1): ya no se depende de la cuenta default de Compute.

> **Nota histórica.** En este proyecto, `gcloud run deploy --source .` falló al principio con `PERMISSION_DENIED ... IAM permission denied for service account ...-compute@developer.gserviceaccount.com`, porque la cuenta de Compute no podía leer el zip de código. Entonces se resolvió dándole `roles/storage.objectViewer`. Con `sa-cloudbuild-segmen` (`roles/run.builder`) ese permiso ya no es necesario y no se otorga. Si se despliega **sin** `--build-service-account`, GCP vuelve a usar la cuenta de Compute y reaparece ese error.

### 3.4. Base de datos Firestore (una sola vez)
Debe crearse **sin `--database`** para obtener la base especial `(default)` (elegible para free tier y la que usa el cliente de Python por defecto):
```bash
gcloud firestore databases create \
  --location=us-central1 --type=firestore-native \
  --project=arl-dtpr-dev-cust-segmen
```
> **Trampa de la consola:** escribir `default` (sin poder teclear los paréntesis) en "Database ID" crea una base **con nombre** (`projects/.../databases/default`), no elegible para free tier y distinta de la que usa el código. Si ocurre, se borra y se recrea con el comando anterior.

---

## 4. Notas de costo

| Servicio | Límite gratuito permanente | Uso en el proyecto |
|---|---|---|
| BigQuery | 1 TB consultas/mes + 10 GB | Decenas de filas por corrida |
| Firestore | 1 GB + 50 K lecturas / 20 K escrituras diarias | Un documento por cliente |
| Cloud Run | 2 M requests/mes | 1 request por ejecución |
| Cloud Functions | 2 M invocaciones/mes | Una por evento |
| Pub/Sub | 10 GB/mes | Mensajes de pocos bytes |
| Cloud Workflows | 5 000 pasos internos/mes | Decenas de pasos por ejecución (depende de la espera de enriquecimiento y del polling) |

Detalle en [`costs-es.md`](costs-es.md).

---

## 5. Cuentas de servicio (IAM)

Convención: `sa-<tipo-de-componente>-<segmento>` — **una cuenta por tipo de componente, no por instancia**. El segmento es `segmen`, el último tramo del Project ID.

| Cuenta | Tipo | Usada por |
|---|---|---|
| `sa-cloudrun-segmen` | Cloud Run | `cr-registration-ingest` |
| `sa-cloudfunction-segmen` | Cloud Function | Las 4 Cloud Functions y sus triggers de Eventarc/Pub/Sub |
| `sa-workflow-segmen` | Workflow | `orquestador-cust-segmen` |
| `sa-scheduledquery-segmen` | Scheduled Query | Las 2 Scheduled Queries |
| `sa-cloudbuild-segmen` | Cloud Build | Deploys de Cloud Run y Cloud Functions (`--build-service-account`) |
| `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com` | Automática (default) | **Ningún componente**; se le retiró `roles/editor` |

> Estado tras el hardening de IAM (24/09/2026): ningún componente depende de la cuenta default de Compute. Verificado con el Workflow en `Succeeded` y dos redespliegues (Cloud Run y una Cloud Function) en `SUCCESS` con `sa-cloudbuild-segmen`. A la cuenta default de App Engine (`arl-dtpr-dev-cust-segmen@appspot.gserviceaccount.com`), que también tenía `roles/editor` y no la usa ningún componente, se le retiró igual y se verificó con el Workflow y los logs de `cf-enrich-and-notify`. Guía completa: `docs/iam-hardening-es.md` (mismo paquete de entrega).

### 5.1. Creación
```bash
for SA in sa-cloudrun-segmen sa-cloudfunction-segmen sa-workflow-segmen; do
  gcloud iam service-accounts create $SA --project=arl-dtpr-dev-cust-segmen
done
```

### 5.2. Permisos de `sa-cloudrun-segmen`
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/pubsub.publisher` | Tópico `customer-registered` | Publicar un evento por cada cliente |

```bash
gcloud pubsub topics add-iam-policy-binding customer-registered \
  --member="serviceAccount:sa-cloudrun-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

### 5.3. Permisos de `sa-cloudfunction-segmen`
| Rol | Alcance | Para qué |
|---|---|---|
| `roles/bigquery.dataEditor` | **Solo el dataset `std_arl_all_randomuser`** (`GRANT ... ON SCHEMA`) | Insertar en `trx_customer_notification` |
| `roles/bigquery.jobUser` | Proyecto | Ejecutar consultas `SELECT` de `cf-route-customer-decision` |
| `roles/datastore.user` | Proyecto | Upsert en Firestore (Firestore Native usa el prefijo `datastore`) |
| `roles/pubsub.publisher` | Tópicos `marketing-events` y `customer-segment-notification` | Republicar/publicar eventos |
| `roles/logging.logWriter` | Proyecto | Logs estructurados |
| `roles/run.invoker` | Cada Cloud Run subyacente de las 3 funciones con trigger de Pub/Sub | Que el trigger de Eventarc/Pub/Sub pueda invocarlas (`cf-route-customer-decision` solo la invoca el Workflow) |

```bash
SA=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com
P=arl-dtpr-dev-cust-segmen

for ROLE in roles/bigquery.jobUser roles/datastore.user roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding $P --member="serviceAccount:$SA" --role="$ROLE"
done

# dataEditor solo sobre el dataset (los GRANT son SQL: se ejecutan con bq query o en BigQuery Studio)
bq query --use_legacy_sql=false --project_id=$P <<'EOF'
GRANT `roles/bigquery.dataEditor` ON SCHEMA `arl-dtpr-dev-cust-segmen.std_arl_all_randomuser`
  TO "serviceAccount:sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com";
EOF

for T in marketing-events customer-segment-notification; do
  gcloud pubsub topics add-iam-policy-binding $T --member="serviceAccount:$SA" --role="roles/pubsub.publisher"
done

# El agente de servicio de Pub/Sub debe poder generar tokens OIDC como esta cuenta
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```
`run.invoker` se otorga **después de desplegar cada función** (sección 8).

### 5.4. Rol personalizado y permisos de `sa-workflow-segmen`
```bash
gcloud iam roles create custSegmenTransferRunner --project=arl-dtpr-dev-cust-segmen \
  --title="Cust Segmen Transfer Runner" \
  --permissions=bigquery.transfers.get,bigquery.transfers.update

W=sa-workflow-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding $P --member="serviceAccount:$W" --role="projects/$P/roles/custSegmenTransferRunner"
gcloud projects add-iam-policy-binding $P --member="serviceAccount:$W" --role="roles/logging.logWriter"
# Paso de espera del Workflow: ejecuta una consulta que cuenta los clientes ya enriquecidos
gcloud projects add-iam-policy-binding $P --member="serviceAccount:$W" --role="roles/bigquery.jobUser"
```
```sql
GRANT `roles/bigquery.dataViewer` ON SCHEMA `arl-dtpr-dev-cust-segmen.std_arl_all_randomuser`
  TO "serviceAccount:sa-workflow-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com";
```
Además necesita `roles/run.invoker` sobre `cr-registration-ingest` y sobre `cf-route-customer-decision` (secciones 7.5 y 8.5).

### 5.4.1. Cuentas de las Scheduled Queries y de Cloud Build (hardening)
```bash
gcloud iam service-accounts create sa-scheduledquery-segmen --project=arl-dtpr-dev-cust-segmen
gcloud iam service-accounts create sa-cloudbuild-segmen --project=arl-dtpr-dev-cust-segmen

gcloud projects add-iam-policy-binding $P \
  --member="serviceAccount:sa-scheduledquery-segmen@$P.iam.gserviceaccount.com" --role="roles/bigquery.jobUser"
gcloud projects add-iam-policy-binding $P \
  --member="serviceAccount:sa-cloudbuild-segmen@$P.iam.gserviceaccount.com" --role="roles/run.builder"
```
```sql
GRANT `roles/bigquery.dataEditor` ON SCHEMA `arl-dtpr-dev-cust-segmen.std_arl_all_randomuser`
  TO "serviceAccount:sa-scheduledquery-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com";
```
Todos los despliegues (`gcloud run deploy` y `gcloud functions deploy`) llevan `--build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com`. `run.builder` alcanza también para builds de Cloud Functions gen2 (verificado).

### 5.5. Regla de oro de IAM en este proyecto
Toda Cloud Function gen2 corre sobre un Cloud Run interno. Sin `roles/run.invoker` sobre ese servicio, el trigger falla con `401 The request was not authenticated` y reintentos con backoff. Los permisos tardan 1–2 minutos en propagarse: ante un `403` recién otorgado, **esperar y reintentar**.

---

## 6. Pub/Sub — detalle de los 3 tópicos

| Tópico | Publica | Consume | Contenido del mensaje |
|---|---|---|---|
| `customer-registered` | `cr-registration-ingest` | `cf-enrich-and-notify` | Registro del cliente: `customer_id`, `email`, `first_name`, `last_name`, `country`, `registered_at` |
| `marketing-events` | `cf-enrich-and-notify` | `cf-forward-to-marketing-platform` | `customer_id`, `email`, `first_name`, `event: "welcome_email"` |
| `customer-segment-notification` | `cf-route-customer-decision` | `cf-notify-segment-consumer` | Cliente clasificado como `special_program` |

```bash
gcloud pubsub topics create customer-registered
gcloud pubsub topics create marketing-events
gcloud pubsub topics create customer-segment-notification
```
Las suscripciones las crea Eventarc automáticamente al desplegar cada función con `--trigger-topic` (aparecen como `eventarc-us-central1-<función>-…-sub-…`). Con política `RETRY_POLICY_DO_NOT_RETRY`, si un webhook falla, ese mensaje **se pierde**, no se reintenta.

---

## 7. Cloud Run — `cr-registration-ingest`

| Campo | Valor |
|---|---|
| Acceso | Privado (`--no-allow-unauthenticated`) |
| Identidad | `sa-cloudrun-segmen` |
| URL | `https://cr-registration-ingest-<PROJECT_NUMBER>.us-central1.run.app` |
| Arquitectura | En capas: `src/app/{main.py, api/routes/registration.py, core/config.py, integrations/{randomuser,pubsub}/main.py, services/registration_service.py, utils/}` |
| Tests | 15, todos pasando |

### 7.1. Qué hace
1. Consulta RandomUser.me pidiendo `BATCH_SIZE` perfiles.
2. Por cada perfil, `clean_record()` lo aplana a un evento: genera un `customer_id` (UUID v4), toma `email`, `first_name`, `last_name`, `country` y fija `registered_at` con la hora UTC de la ingesta.
3. `is_valid_record()` descarta registros sin email válido (con `@`), sin nombre o sin `customer_id`.
4. Publica cada registro válido en `customer-registered`.
5. Responde con el conteo de publicados y omitidos.

### 7.2. Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `PROJECT_ID` | `arl-dtpr-dev-cust-segmen` | Proyecto |
| `SERVICE_NAME` | `cr-registration-ingest` | Nombre para logs y respuesta |
| `RANDOM_USER_URL` | `https://randomuser.me/api/` | API fuente |
| `BATCH_SIZE` | `5` (valor actual desplegado: `30`) | Cantidad de clientes por ejecución |
| `PUBSUB_TOPIC` | `customer-registered` | Tópico de salida |

> **Valor actual: `BATCH_SIZE=30`** (`gcloud run services update ... --update-env-vars=BATCH_SIZE=30`, revisión `cr-registration-ingest-00009-bzc`). El valor por defecto del código es 5. Con 30 clientes por corrida el segundo tramo es visible (~12 % en `special_program`), pero cada corrida consume 30 requests del webhook de marketing, así que se usa con URLs de webhook.site nuevas (sección 12).

### 7.3. Despliegue
```bash
gcloud run deploy cr-registration-ingest \
  --source cloud-run/cr-registration-ingest \
  --region us-central1 \
  --no-allow-unauthenticated \
  --service-account=sa-cloudrun-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,SERVICE_NAME=cr-registration-ingest,RANDOM_USER_URL=https://randomuser.me/api/,BATCH_SIZE=30,PUBSUB_TOPIC=customer-registered
```

### 7.4. Cambiar solo variables sin redesplegar código
```bash
gcloud run services update cr-registration-ingest --region=us-central1 \
  --project=arl-dtpr-dev-cust-segmen --update-env-vars=BATCH_SIZE=30   # 5 = valor por defecto del código; 30 = valor actual
```

### 7.5. Permiso para el Workflow
```bash
gcloud run services add-iam-policy-binding cr-registration-ingest --region=us-central1 \
  --member="serviceAccount:sa-workflow-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 7.6. Prueba directa
```bash
curl -X POST https://cr-registration-ingest-<PROJECT_NUMBER>.us-central1.run.app/ \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
# {"payload":{"ingestion_timestamp":"...","published":30,"skipped":0},"service":"cr-registration-ingest","status":"success"}
```

---

## 8. Cloud Functions (las 4)

Todas: gen2, Python 3.12, región `us-central1`, identidad `sa-cloudfunction-segmen`, sin acceso público. Comparten la **arquitectura plana**:
```
main.py                # from src.main import main
src/
├── config.py          # variables de entorno con default
├── gcp_logging.py     # GCPLogger: JSON en Cloud, texto plano en local
├── main.py            # punto de entrada con try/except y banners de log
└── utils.py           # lógica de negocio
tests/                 # conftest.py mockea BigQuery/Firestore/Pub/Sub antes de importar
```

### 8.1. `cf-enrich-and-notify`

| Campo | Valor |
|---|---|
| Trigger | Pub/Sub → `customer-registered` (signature type `event`) |
| Tests | 11 |

**Qué hace, paso a paso:**
1. `decode_pubsub_message()` decodifica el payload base64 del evento.
2. `enrich_record()` agrega `enriched_at` (UTC actual) y `prospect_status = "new"`.
3. `log_notification()` inserta la fila en `std_arl_all_randomuser.trx_customer_notification` (`insert_rows_json`).
4. `upsert_prospect()` hace `set(..., merge=True)` en Firestore, documento con clave `customer_id`, colección `customer_prospects`.
5. `publish_marketing_event()` publica `{customer_id, email, first_name, event: "welcome_email"}` en `marketing-events`.
6. Escribe banners `INICIO/FIN cf-enrich-and-notify OK` y, ante cualquier excepción, registra el error y la relanza.

| Variable | Default |
|---|---|
| `PROJECT_ID` | `arl-dtpr-dev-cust-segmen` |
| `REGION` | `us-central1` |
| `SERVICE_NAME` | `cf-enrich-and-notify` |
| `BQ_DATASET` | `std_arl_all_randomuser` |
| `BQ_TABLE` | `trx_customer_notification` |
| `FIRESTORE_COLLECTION` | `customer_prospects` |
| `OUTPUT_PUBSUB_TOPIC` | `marketing-events` |

```bash
gcloud functions deploy cf-enrich-and-notify \
  --gen2 --runtime=python312 --region=us-central1 --source=. \
  --entry-point=main --trigger-topic=customer-registered \
  --service-account=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,REGION=us-central1,SERVICE_NAME=cf-enrich-and-notify,BQ_DATASET=std_arl_all_randomuser,BQ_TABLE=trx_customer_notification,FIRESTORE_COLLECTION=customer_prospects,OUTPUT_PUBSUB_TOPIC=marketing-events
```

### 8.2. `cf-forward-to-marketing-platform`

| Campo | Valor |
|---|---|
| Trigger | Pub/Sub → `marketing-events` (`event`) |
| Tests | 9 |

**Qué hace:** decodifica el evento y hace `POST` con `requests` al webhook `MARKETING_WEBHOOK_URL` (simula una plataforma de marketing tipo Salesforce Marketing Cloud) con un timeout configurable. Si el webhook responde con estado ≥ 300 lanza `RuntimeError`.

| Variable | Default |
|---|---|
| `PROJECT_ID` / `REGION` | `arl-dtpr-dev-cust-segmen` / `us-central1` |
| `SERVICE_NAME` | `cf-forward-to-marketing-platform` |
| `MARKETING_WEBHOOK_URL` | `https://webhook.site/CHANGE-ME` (se configura al desplegar) |
| `WEBHOOK_TIMEOUT_SECONDS` | `10` |

```bash
gcloud functions deploy cf-forward-to-marketing-platform \
  --gen2 --runtime=python312 --region=us-central1 --source=. \
  --entry-point=main --trigger-topic=marketing-events \
  --service-account=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,REGION=us-central1,SERVICE_NAME=cf-forward-to-marketing-platform,MARKETING_WEBHOOK_URL=https://webhook.site/<TU-URL-1>,WEBHOOK_TIMEOUT_SECONDS=10
```

### 8.3. `cf-notify-segment-consumer`

| Campo | Valor |
|---|---|
| Trigger | Pub/Sub → `customer-segment-notification` (`event`) |
| Tests | 9 |

**Qué hace:** decodifica el evento y hace `POST` al webhook `SEGMENT_CONSUMER_WEBHOOK_URL`, que simula el sistema externo que gestiona el programa especial.

| Variable | Default |
|---|---|
| `PROJECT_ID` / `REGION` | `arl-dtpr-dev-cust-segmen` / `us-central1` |
| `SERVICE_NAME` | `cf-notify-segment-consumer` |
| `SEGMENT_CONSUMER_WEBHOOK_URL` | `https://webhook.site/CHANGE-ME` |
| `WEBHOOK_TIMEOUT_SECONDS` | `10` |

```bash
gcloud functions deploy cf-notify-segment-consumer \
  --gen2 --runtime=python312 --region=us-central1 --source=. \
  --entry-point=main --trigger-topic=customer-segment-notification \
  --service-account=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,REGION=us-central1,SERVICE_NAME=cf-notify-segment-consumer,SEGMENT_CONSUMER_WEBHOOK_URL=https://webhook.site/<TU-URL-2>,WEBHOOK_TIMEOUT_SECONDS=10
```

### 8.4. `cf-route-customer-decision`

| Campo | Valor |
|---|---|
| Trigger | HTTP (signature type `http`) |
| URL directa | `<URL_CF_ROUTE_CUSTOMER_DECISION>` (`gcloud run services describe cf-route-customer-decision --region=us-central1 --format="value(status.url)"`) |
| Tests | 12 |

**Qué hace:**
1. Lee `evaluation_started_at` del cuerpo JSON de la petición (lo envía el Workflow, tomado justo antes de lanzar `sq_evaluate_customer_segment`). Si falta, responde HTTP 400.
2. `get_special_program_customers(evaluation_started_at)` consulta `trx_customer_segment_decision` con `decision = 'special_program'` y `decided_at >= @evaluation_started_at`: solo las decisiones de **esa corrida**, no las del día.
3. `publish_segment_notification(customer_id)` publica un mensaje por cliente en `customer-segment-notification`.
4. Responde `{"routed": N}` con HTTP 200.

| Variable | Default |
|---|---|
| `PROJECT_ID` / `REGION` | `arl-dtpr-dev-cust-segmen` / `us-central1` |
| `SERVICE_NAME` | `cf-route-customer-decision` |
| `BQ_DATASET` | `std_arl_all_randomuser` |
| `BQ_TABLE` | `trx_customer_segment_decision` |
| `OUTPUT_PUBSUB_TOPIC` | `customer-segment-notification` |

```bash
gcloud functions deploy cf-route-customer-decision \
  --gen2 --runtime=python312 --region=us-central1 --source=. \
  --entry-point=main --trigger-http \
  --service-account=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --build-service-account=projects/arl-dtpr-dev-cust-segmen/serviceAccounts/sa-cloudbuild-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,REGION=us-central1,SERVICE_NAME=cf-route-customer-decision,BQ_DATASET=std_arl_all_randomuser,BQ_TABLE=trx_customer_segment_decision,OUTPUT_PUBSUB_TOPIC=customer-segment-notification
```

### 8.5. Permisos `run.invoker` tras cada despliegue
```bash
SA=sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com
for F in cf-enrich-and-notify cf-forward-to-marketing-platform cf-notify-segment-consumer; do
  gcloud run services add-iam-policy-binding $F --region=us-central1 \
    --member="serviceAccount:$SA" --role="roles/run.invoker"
done

# cf-route-customer-decision no tiene trigger de Pub/Sub: solo la invoca el Workflow
gcloud run services add-iam-policy-binding cf-route-customer-decision --region=us-central1 \
  --member="serviceAccount:sa-workflow-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 8.6. Cambiar variables sin código fuente
`gcloud functions deploy` sin `--source` falla si no estás en la carpeta de la función (`Invalid value for [--source]`). Para cambiar solo variables (por ejemplo, un webhook nuevo):
```bash
gcloud run services update cf-forward-to-marketing-platform --region=us-central1 \
  --project=arl-dtpr-dev-cust-segmen --update-env-vars=MARKETING_WEBHOOK_URL=https://webhook.site/<NUEVA-URL>
```

### 8.7. Pruebas
```bash
cd cloud-functions/<nombre-de-la-función>
pip install -r requirements.txt pytest
pytest tests/ -v
```

---

## 9. BigQuery — dataset `std_arl_all_randomuser` (región `US`)

### 9.1. `trx_customer_notification`
Un registro por cliente enriquecido. Particionada por `DATE(registered_at)`, clusterizada por `customer_id`.

| Columna | Tipo | Descripción |
|---|---|---|
| `customer_id` | STRING NOT NULL | UUID generado en la ingesta |
| `email` | STRING NOT NULL | Correo (simulado) |
| `first_name` / `last_name` | STRING | Nombre y apellido |
| `country` | STRING | País según la fuente |
| `registered_at` | TIMESTAMP NOT NULL | Registro simulado (UTC); partición |
| `enriched_at` | TIMESTAMP NOT NULL | Enriquecimiento (UTC) |
| `prospect_status` | STRING | Estado (`'new'`) |

### 9.2. `ori_mtr_program_enrollment`
Dato sintético del negocio, reproducible por hash del `customer_id`; sin datos reales ni financieros.

| Columna | Tipo | Descripción |
|---|---|---|
| `customer_id` | STRING NOT NULL | FK a `trx_customer_notification` |
| `is_enrolled_program` | BOOL NOT NULL | ~40 % `true` |
| `account_tier` | STRING NOT NULL | `basic` o `premium` (~30 % premium) |
| `generated_at` | TIMESTAMP NOT NULL | Momento de generación (UTC) |

### 9.3. `trx_customer_segment_decision`
Una decisión por cliente. Particionada por `DATE(decided_at)`, clusterizada por `customer_id`.

| Columna | Tipo | Descripción |
|---|---|---|
| `customer_id` | STRING NOT NULL | FK a `trx_customer_notification` |
| `decision` | STRING NOT NULL | `marketing_only` o `special_program` |
| `decided_at` | TIMESTAMP NOT NULL | Momento de evaluación (UTC); partición |

### 9.4. Creación
```bash
bq --location=US mk --dataset arl-dtpr-dev-cust-segmen:std_arl_all_randomuser
bq query --use_legacy_sql=false < bigquery/trx_customer_notification.sql
bq query --use_legacy_sql=false < bigquery/ori_mtr_program_enrollment.sql
bq query --use_legacy_sql=false < bigquery/trx_customer_segment_decision.sql
```

---

## 10. Firestore — colección `customer_prospects`

| Campo | Valor |
|---|---|
| Base | `(default)`, Native mode, Standard Edition, `us-central1` |
| Colección | `customer_prospects` |
| Clave del documento | `customer_id` |
| Escrita por | `cf-enrich-and-notify` (`set(..., merge=True)`) |

**Qué representa:** el **estado actual** de cada prospecto (se actualiza, no acumula historial; el histórico vive en BigQuery).
```json
{
  "customer_id": "0505d06d-ad14-4905-88b4-312671cb24db",
  "email": "kay.fournier@example.com",
  "first_name": "Kay",
  "last_name": "Fournier",
  "country": "Switzerland",
  "registered_at": "2026-09-21T21:43:27.187913+00:00",
  "enriched_at": "2026-09-21T21:43:31.699201+00:00",
  "prospect_status": "new"
}
```
**Limpieza para una prueba limpia:** no existe un `TRUNCATE`; en la consola, colección → menú ⋮ → **Delete collection** → confirmar escribiendo el nombre. Es opcional (solo cosmético).

---

## 11. BigQuery Scheduled Queries (2)

Ambas en modo **On-demand**, ubicación `us`, identidad = `sa-scheduledquery-segmen` (antes: la cuenta default de Compute en `sq_generate_synthetic_enrollment` y las credenciales del usuario en `sq_evaluate_customer_segment`). Se crean pegando el SQL en BigQuery Studio, ejecutándolo una vez y usando **Schedule → Create new scheduled query**.

> **Al cambiar la cuenta (siempre por la consola):** Edit → Schedule → Update scheduled query. Antes de **Save**, poner **Repeat frequency = On-demand**; si no, el panel puede activar un horario `every 1 hours`. `bq update --service_account_name` no es fiable (reporta éxito sin aplicar el cambio). Para confirmar la identidad real, consultar `user_email` de los jobs `scheduled_query_*` en `INFORMATION_SCHEMA.JOBS_BY_PROJECT`. Sus `transferConfigId` se obtienen con `bq ls --transfer_config --transfer_location=us --project_id=arl-dtpr-dev-cust-segmen`.

### 11.1. `sq_generate_synthetic_enrollment`
Config ID: `<ID_SQ_SYNTHETIC_ENROLLMENT>`. **Debe correr antes** de la evaluación.

Genera, para cada cliente de `trx_customer_notification` que aún no tenga inscripción, valores sintéticos por hash:
```sql
INSERT INTO `std_arl_all_randomuser.ori_mtr_program_enrollment` (customer_id, is_enrolled_program, account_tier, generated_at)
SELECT L.customer_id,
       MOD(ABS(FARM_FINGERPRINT(CONCAT(L.customer_id, '|enrollment'))), 10) < 4 AS is_enrolled_program,
       IF(MOD(ABS(FARM_FINGERPRINT(CONCAT(L.customer_id, '|tier'))), 10) < 3, 'premium', 'basic') AS account_tier,
       CURRENT_TIMESTAMP()
FROM `std_arl_all_randomuser.trx_customer_notification` L
LEFT JOIN `std_arl_all_randomuser.ori_mtr_program_enrollment` S ON L.customer_id = S.customer_id
WHERE S.customer_id IS NULL;
```
- **Idempotente** gracias al `LEFT JOIN ... WHERE S.customer_id IS NULL`.
- **Determinística**: el mismo `customer_id` siempre produce el mismo resultado.
- **Un hash por atributo**: `CONCAT(customer_id, '|enrollment')` y `CONCAT(customer_id, '|tier')`. Con el mismo hash para ambos, todo cliente premium resultaba también inscrito y `special_program` daba ~30 % en vez de ~12 % (simulación de 100 000 clientes: 30.1 % contra 11.8 % con hashes independientes). Verificado en GCP el 25/09/2026: las cuatro combinaciones de inscrito y nivel aparecen, incluidos clientes premium sin inscribir.
- **No proviene de ninguna API**: se calcula dentro de BigQuery a propósito, porque en un caso real el dato equivalente sería financiero y sensible y no debe aparecer en una demo pública.

### 11.2. `sq_evaluate_customer_segment`
Config ID: `<ID_SQ_EVALUATE_CUSTOMER_SEGMENT>`.

`MERGE` que aplica la regla de negocio y solo inserta decisiones nuevas:
```sql
MERGE `std_arl_all_randomuser.trx_customer_segment_decision` T
USING (
  SELECT L.customer_id,
         IF(S.is_enrolled_program AND S.account_tier = 'premium', 'special_program', 'marketing_only') AS decision,
         CURRENT_TIMESTAMP() AS decided_at
  FROM `std_arl_all_randomuser.trx_customer_notification` L
  JOIN `std_arl_all_randomuser.ori_mtr_program_enrollment` S ON L.customer_id = S.customer_id
) S
ON T.customer_id = S.customer_id
WHEN NOT MATCHED THEN INSERT (customer_id, decision, decided_at) VALUES (S.customer_id, S.decision, S.decided_at);
```
No filtra por `DATE(registered_at) = CURRENT_DATE()` para que las pruebas manuales no dependan de la fecha; el `MERGE` sigue siendo idempotente.

---

## 12. Webhooks externos simulados

| Componente | Simula | Variable |
|---|---|---|
| `cf-forward-to-marketing-platform` | Plataforma de marketing (tipo Salesforce Marketing Cloud) | `MARKETING_WEBHOOK_URL` |
| `cf-notify-segment-consumer` | Sistema externo del programa especial | `SEGMENT_CONSUMER_WEBHOOK_URL` |

**Limitación importante de webhook.site (gratis, sin cuenta):** tope **de por vida de 50 requests almacenados por URL**. Al alcanzarlo, todo request devuelve `429 Request limit exceeded` de forma permanente. Solución: generar una URL nueva y actualizarla con `gcloud run services update ... --update-env-vars=...`. Como los tópicos no reintentan, los mensajes rechazados se pierden. Cada ejecución del Workflow publica `BATCH_SIZE` eventos al webhook de marketing (30 con el valor actual), y `cf-route-customer-decision` notifica solo las decisiones `special_program` de esa corrida, así que el segundo webhook recibe únicamente los clientes nuevos (no se repiten entre corridas). Con `BATCH_SIZE=30` conviene una URL de marketing nueva cada dos corridas como máximo. Corrida de referencia del 25/09/2026: 30 requests en marketing y 3 en el consumidor.

---

## 13. Cloud Workflow — `orquestador-cust-segmen`

| Campo | Valor |
|---|---|
| Región | `us-central1` |
| Identidad | `sa-workflow-segmen` |
| Definición | `workflow/orquestador-cust-segmen.yaml` |
| Variables | `workflow/env.yaml` |

### 13.1. Variables de entorno del Workflow (11)

| Variable | Valor |
|---|---|
| `project_id` | `arl-dtpr-dev-cust-segmen` |
| `project_number` | `<PROJECT_NUMBER>` |
| `region` | `us-central1` |
| `transfer_location` | `us` |
| `cloud_run_service_name` | `cr-registration-ingest` |
| `transfer_config_id_enrollment` | `<ID_SQ_SYNTHETIC_ENROLLMENT>` |
| `transfer_config_id_segment` | `<ID_SQ_EVALUATE_CUSTOMER_SEGMENT>` |
| `poll_interval_seconds` | `10` |
| `cf_route_customer_decision_url` | `<URL_CF_ROUTE_CUSTOMER_DECISION>` |
| `bq_dataset` | `std_arl_all_randomuser` |
| `enrichment_max_attempts` | `30` (con `poll_interval_seconds=10`: espera máxima de unos 5 minutos) |

### 13.2. Estructura
Incluye un **subworkflow** `poll_transfer_run` (parámetros `transfer_run_name`, `poll_interval_seconds`) que consulta el estado de una ejecución cada N segundos y devuelve `SUCCEEDED` o levanta error con el detalle si termina en `FAILED`/`CANCELLED`. Se reutiliza para las dos Scheduled Queries, evitando duplicar la lógica. Un segundo subworkflow, `wait_for_enrichment` (parámetros `project_id`, `bq_dataset`, `since`, `expected`, `poll_interval_seconds`, `max_attempts`), cuenta en `trx_customer_notification` los clientes con `enriched_at >= since` y espera hasta igualar los publicados; si se agota el tiempo, falla con un error explícito.

| Paso | Qué hace |
|---|---|
| `init` | Lee las 11 variables y construye la URL de Cloud Run y los nombres de ambos transfer configs |
| `call_registration_ingest` | `http.post` OIDC a `cr-registration-ingest`, con `try/except` que expone el error real |
| `log_ingest_result` / `check_ingest_status` | Registra la respuesta y exige `body.status == "success"` |
| `extract_ingest_info` → `wait_enrichment` | Toma `published` e `ingestion_timestamp` de la respuesta de Cloud Run y espera (`wait_for_enrichment`) a que esos clientes estén en `trx_customer_notification` |
| `trigger_sq_enrollment` → `extract_enrollment_run_name` → `poll_enrollment` | Dispara `sq_generate_synthetic_enrollment` y espera a que termine |
| `mark_evaluation_start` | Guarda la hora de inicio de la evaluación (`evaluation_started_at`) |
| `trigger_sq_segment` → `extract_segment_run_name` → `poll_segment` | Dispara `sq_evaluate_customer_segment` (después de la anterior) y espera |
| `call_route_decision` | `http.post` OIDC a `cf-route-customer-decision` con `evaluation_started_at` en el cuerpo, con `try/except` |
| `log_route_result` | Registra la respuesta |
| `workflow_success` | Devuelve los resultados, incluido `enriched_customers` |

### 13.3. Resultado esperado
```json
{
  "enriched_customers": 30,
  "enrollment_query_final_state": "SUCCEEDED",
  "ingest_result": {"payload": {"ingestion_timestamp": "2026-09-25T18:58:51.660944+00:00", "published": 30, "skipped": 0}, "service": "cr-registration-ingest", "status": "success"},
  "route_result": {"routed": 3},
  "segment_query_final_state": "SUCCEEDED"
}
```
`enriched_customers` debe ser igual a `published` (o mayor, si Pub/Sub reentrega). `routed` puede ser 0 en una corrida si ningún cliente cayó en `special_program`; es un resultado válido, no un error. Este resultado es el de la corrida del 25/09/2026 (ejecución de 3 minutos, revisión `000004-09a`).

### 13.4. Creación (siempre por la consola)
1. **Workflows → Create**.
2. Nombre `orquestador-cust-segmen`, descripción, región `us-central1`, service account `sa-workflow-segmen`.
3. En **Environment variables**, cargar las 11 variables de 13.1 (verificar que no queden variables de otro proyecto).
4. **Next** → pegar el YAML → **Deploy**.

### 13.5. Ejecución (siempre con el botón Execute)
Workflows → `orquestador-cust-segmen` → **Execute** con entrada `{}`.

### 13.6. Errores típicos del Workflow
| Error | Causa | Solución |
|---|---|---|
| `TypeError: unsupported operand types for +: 'str' and 'null'` en `init` | Faltan variables o hay variables de otro proyecto | Revisar las 11 variables de 13.1 |
| `403 Forbidden ... insufficient_scope` | Barra `/` final en la URL de Cloud Run (audience OIDC distinto) | Construir la URL sin `/` final |
| `IAM permission denied for service account sa-workflow-segmen` | Falta `run.invoker` o aún no se propagó | Otorgarlo y esperar 1–2 min |
| `Tiempo agotado esperando el enriquecimiento: X de N clientes` | La cascada Pub/Sub → `cf-enrich-and-notify` no terminó a tiempo o falló | Revisar los logs de `cf-enrich-and-notify` y, si hace falta, subir `enrichment_max_attempts` |
| `403` en la consulta del paso de espera | Falta `bigquery.jobUser` (proyecto) o `dataViewer` (dataset) en `sa-workflow-segmen` | Otorgarlos (sección 5.4) |

---

## 14. Checklist de verificación (capturas para el documento E2E)

- [ ] `orquestador-cust-segmen`: ejecución con estado `Succeeded`, `Output` completo (`enriched_customers` igual a `published`) y el subworkflow `wait_for_enrichment` visible
- [ ] `cr-registration-ingest`: logs con `Consultando RandomUser.me` y un `Evento publicado` por cliente
- [ ] `customer-registered`: suscripción de Eventarc hacia `cf-enrich-and-notify`
- [ ] `cf-enrich-and-notify`: métricas/logs con `FIN cf-enrich-and-notify OK`
- [ ] `trx_customer_notification` con las filas del lote
- [ ] Firestore `customer_prospects` con un documento por cliente
- [ ] `marketing-events`: suscripción hacia `cf-forward-to-marketing-platform`
- [ ] `cf-forward-to-marketing-platform`: logs `Plataforma de marketing notificada`
- [ ] Scheduled Query `sq_generate_synthetic_enrollment`: ejecución exitosa
- [ ] `ori_mtr_program_enrollment` con `is_enrolled_program` y `account_tier`
- [ ] Scheduled Query `sq_evaluate_customer_segment`: ejecución exitosa
- [ ] `trx_customer_segment_decision` con ambos valores (`marketing_only` y `special_program`)
- [ ] `cf-route-customer-decision`: logs `Decisiones evaluadas desde: ...` y `Clientes special_program encontrados: N`
- [ ] `customer-segment-notification`: suscripción hacia `cf-notify-segment-consumer`
- [ ] `cf-notify-segment-consumer`: log `Consumidor de segmento notificado`
- [ ] Requests recibidos en los dos webhooks (`BATCH_SIZE` en el de marketing; solo los `special_program` de la corrida en el del consumidor)

### 14.1. Prueba limpia (E2E desde cero)
```sql
TRUNCATE TABLE `std_arl_all_randomuser.trx_customer_notification`;
TRUNCATE TABLE `std_arl_all_randomuser.ori_mtr_program_enrollment`;
TRUNCATE TABLE `std_arl_all_randomuser.trx_customer_segment_decision`;
```
Se usa `TRUNCATE`, nunca `DROP`. Firestore se limpia manualmente (sección 10), y conviene generar URLs nuevas de webhook.site si la anterior se acercó a 50 requests. Es la prueba que se hizo el 25/09/2026 (`BATCH_SIZE=30`): las 3 tablas quedaron con 30 filas y la decisión con 27 `marketing_only` y 3 `special_program`.

### 14.2. Prueba manual paso a paso (sin Workflow)
```bash
# 1. Ingesta (dispara el primer tramo)
curl -X POST https://cr-registration-ingest-<PROJECT_NUMBER>.us-central1.run.app/ \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
gcloud functions logs read cf-enrich-and-notify --region=us-central1 --gen2 --limit=30

# 2. Scheduled Queries en orden (BigQuery → Scheduled queries → Run transfer now):
#    sq_generate_synthetic_enrollment, luego sq_evaluate_customer_segment

# 3. Enrutamiento (dispara el segundo tramo); evaluation_started_at es obligatorio
curl -X POST <URL_CF_ROUTE_CUSTOMER_DECISION> \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"evaluation_started_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}'
gcloud functions logs read cf-notify-segment-consumer --region=us-central1 --gen2 --limit=20
```

---

## 15. Resumen de variables por componente

| Componente | Variables |
|---|---|
| `cr-registration-ingest` | `PROJECT_ID`, `SERVICE_NAME`, `RANDOM_USER_URL`, `BATCH_SIZE`, `PUBSUB_TOPIC` |
| `cf-enrich-and-notify` | `PROJECT_ID`, `REGION`, `SERVICE_NAME`, `BQ_DATASET`, `BQ_TABLE`, `FIRESTORE_COLLECTION`, `OUTPUT_PUBSUB_TOPIC` |
| `cf-forward-to-marketing-platform` | `PROJECT_ID`, `REGION`, `SERVICE_NAME`, `MARKETING_WEBHOOK_URL`, `WEBHOOK_TIMEOUT_SECONDS` |
| `cf-route-customer-decision` | `PROJECT_ID`, `REGION`, `SERVICE_NAME`, `BQ_DATASET`, `BQ_TABLE`, `OUTPUT_PUBSUB_TOPIC` |
| `cf-notify-segment-consumer` | `PROJECT_ID`, `REGION`, `SERVICE_NAME`, `SEGMENT_CONSUMER_WEBHOOK_URL`, `WEBHOOK_TIMEOUT_SECONDS` |
| Workflow | `project_id`, `project_number`, `region`, `transfer_location`, `cloud_run_service_name`, `transfer_config_id_enrollment`, `transfer_config_id_segment`, `poll_interval_seconds`, `cf_route_customer_decision_url`, `bq_dataset`, `enrichment_max_attempts` |

---

## 16. Evolución frente a la versión 1

| Aspecto | v1 | v2 (`arl-dtpr-dev-cust-segmen`) |
|---|---|---|
| Nombres | `registration-ingest`, `crm_dw`, `customer_notification_log` | Taxonomía completa: `cr-registration-ingest`, `std_arl_all_randomuser`, `trx_/ori_` |
| Acceso | `--allow-unauthenticated` | Todo privado, con identidades por tipo de componente |
| Ejecución | Cloud Scheduler + Scheduled Queries sueltas | Un Workflow que ejecuta todo, espera el enriquecimiento y espera cada Scheduled Query |
| Cloud Functions | Estructura simple | Arquitectura plana con `GCPLogger`, tests con mocks y variables de entorno |
| Firestore | Base por defecto | Base `(default)` creada explícitamente por `gcloud` |
| Webhooks | Una URL de prueba | Dos URLs distintas, con manejo del tope de webhook.site |

---

## 17. Orden recomendado de despliegue desde cero

1. Crear proyecto y habilitar APIs (sección 3). No hace falta dar permisos a la cuenta de Compute: los builds usan `sa-cloudbuild-segmen`.
2. Crear Firestore `(default)` por `gcloud` (3.4).
3. Crear los 3 tópicos Pub/Sub (sección 6).
4. Crear dataset y tablas de BigQuery (sección 9).
5. Crear las 5 cuentas de servicio (`sa-cloudrun-segmen`, `sa-cloudfunction-segmen`, `sa-workflow-segmen`, `sa-scheduledquery-segmen`, `sa-cloudbuild-segmen`) y sus permisos (sección 5), con `dataEditor` solo por dataset. Al final, comprobar que las cuentas default de Compute y de App Engine no conservan `roles/editor`.
6. Desplegar `cr-registration-ingest` (sección 7).
7. Generar 2 URLs en webhook.site y desplegar las 4 Cloud Functions; otorgar `run.invoker` a cada una (sección 8).
8. Crear las 2 Scheduled Queries y anotar sus `transferConfigId` (sección 11).
9. Crear el Workflow desde la consola con sus 11 variables (sección 13). Sus permisos incluyen `bigquery.jobUser` y `dataViewer` sobre el dataset (sección 5.4).
10. Ejecutarlo con **Execute** y completar el checklist (sección 14).

---

## 18. Correcciones tras la revisión (25/09/2026)

| # | Problema encontrado | Corrección | Verificación |
|---|---|---|---|
| 1 | Los dos atributos sintéticos compartían el mismo hash: todo premium salía inscrito y `special_program` daba ~30 % en vez de ~12 % | Hash independiente por atributo (`'|enrollment'` y `'|tier'`) en `sq_generate_synthetic_enrollment` | 30 clientes: aparecen las 4 combinaciones (incluidos 4 premium sin inscribir); 3 `special_program` (10 %) |
| 2 | Condición de carrera: el Workflow lanzaba las Scheduled Queries sin esperar a que la cascada Pub/Sub → `cf-enrich-and-notify` → BigQuery terminara (30 clientes en `trx_customer_notification` y solo 11 con decisión) | Paso `wait_enrichment` con polling y tiempo máximo; `sa-workflow-segmen` recibe `bigquery.jobUser` y `dataViewer` sobre el dataset | `enriched_customers: 30` = `published: 30`; las 3 tablas quedan con 30 filas |
| 3 | `cf-route-customer-decision` filtraba por `DATE(decided_at) = CURRENT_DATE()` y re-notificaba a todos los `special_program` del día en cada corrida | El Workflow envía `evaluation_started_at`; la función filtra `decided_at >= @evaluation_started_at` (12 tests, tres nuevos) | `routed: 3` en la corrida y 3 requests en el webhook del consumidor |
| 4 | Versión de Python del Cloud Run documentada como 3.12 | El Dockerfile usa `python:3.11-slim`; documentación y diagrama corregidos (las Cloud Functions usan 3.12) | — |
| 5 | `workflow/env.yaml` no era YAML válido y traía valores propios del proyecto | Ahora es YAML válido, con marcadores `<...>` para número de proyecto, IDs de las Scheduled Queries y URL de la función | — |
| 6 | Rutas con espacios (`cloud run/`, `cloud function/`, `service account/`) | Estructura del repositorio: `cloud-run/`, `cloud-functions/`, `bigquery/`, `scheduled-queries/`, `workflow/`, `docs/` | — |
| 7 | Documento de costos desactualizado y registro de cuentas con el número de proyecto | Costos reescrito; número de proyecto sustituido por `<PROJECT_NUMBER>` | — |

Evidencia de la corrida de verificación: ejecución `a98dc275-f085-4c0a-b8c1-35de1f7243ab` del Workflow (`Succeeded`, 3 minutos), tablas con 30 filas, decisiones 27 `marketing_only` y 3 `special_program`, webhooks con 30 y 3 requests.
