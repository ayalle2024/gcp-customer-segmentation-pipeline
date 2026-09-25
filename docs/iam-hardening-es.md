# Hardening IAM — `arl-dtpr-dev-cust-segmen`
## Eliminar la dependencia de la cuenta default de Compute (`roles/editor`)

Aplica a este proyecto el mismo hardening de IAM hecho en el proyecto Weather ([`gcp-weather-elt-pipeline`](https://github.com/ayalle2024/gcp-weather-elt-pipeline)).

**Objetivo:** que ningún componente del pipeline use `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`. Hoy la usan **Cloud Build** (cada `gcloud run deploy` y `gcloud functions deploy`) y las **2 Scheduled Queries**, y esa cuenta tiene `roles/editor` sobre todo el proyecto. De paso se baja el `bigquery.dataEditor` de `sa-cloudfunction-segmen` de **proyecto** a **dataset**.

## 1. Qué cambia respecto a Weather

| Tema | Weather | Customer Segmentation |
|---|---|---|
| Scheduled Queries | 1 (lee `raw_`/`std_`, escribe `std_`/`trf_`) | **2** (`sq_generate_synthetic_enrollment`, `sq_evaluate_customer_segment`), ambas leen y escriben **un solo dataset**: `std_arl_all_randomuser` |
| Cuenta de las Scheduled Queries | `sa-weather-sq-runtime` | **una sola** cuenta compartida por las 2: `sa-scheduledquery-segmen` (una cuenta por *tipo* de componente) |
| Componentes que usan Cloud Build | 1 Cloud Run | 1 Cloud Run + **4 Cloud Functions gen2** |
| Cuenta con `dataEditor` de proyecto a acotar | `sa-weather-cloudrun-runtime` | `sa-cloudfunction-segmen` (el Cloud Run de este proyecto no toca BigQuery) |
| Convención de nombres | `sa-weather-*` | `sa-<tipo>-segmen`, igual que las existentes |
| Riesgo extra | — | Cuota de webhook.site (50 requests por URL): cada Execute del Workflow consume ~30 con `BATCH_SIZE=30` |

## 2. Estado final

| Cuenta | Usada por | Permisos |
|---|---|---|
| `sa-cloudrun-segmen` | `cr-registration-ingest` | `pubsub.publisher` en `customer-registered` *(sin cambios)* |
| `sa-cloudfunction-segmen` | Las 4 Cloud Functions y sus triggers | `bigquery.jobUser` (proyecto) + `bigquery.dataEditor` **solo en `std_arl_all_randomuser`** + `datastore.user` + `pubsub.publisher` (2 tópicos) + `logging.logWriter` + `run.invoker` (x4 servicios) |
| `sa-workflow-segmen` | El Workflow | `run.invoker` (Cloud Run y `cf-route-customer-decision`) + `custSegmenTransferRunner` + `logging.logWriter` *(sin cambios)* |
| `sa-scheduledquery-segmen` **(nueva)** | Las 2 Scheduled Queries | `bigquery.jobUser` (proyecto) + `bigquery.dataEditor` en `std_arl_all_randomuser` |
| `sa-cloudbuild-segmen` **(nueva)** | Cloud Build (despliegues de Cloud Run y Cloud Functions) | `roles/run.builder` |
| `<PROJECT_NUMBER>-compute@…` | **Nadie** | Se le retira `roles/editor` |

Orden: primero lo aditivo (cuentas y permisos), luego los cambios de comportamiento con prueba después de cada uno, y **al final** los retiros.

---

## 3. Antes de empezar

### 3.1. Reducir el consumo del webhook
Cada Execute publica `BATCH_SIZE` eventos hacia el webhook de marketing (más los del segmento especial). Con 30, dos o tres pruebas agotan el tope de 50 requests por URL. Durante el hardening se usó 5 (estado actual: 30, ver la sección 8):
```bash
gcloud run services update cr-registration-ingest --region=us-central1 \
  --project=arl-dtpr-dev-cust-segmen --update-env-vars=BATCH_SIZE=5
```
Con 5 clientes es posible que ningún cliente sea `special_program` (~12 %) y `routed` salga 0: es un resultado válido, no un error. Al terminar, se puede volver a `BATCH_SIZE=30` con URLs de webhook nuevas.

### 3.2. Estado actual (solo lectura)
```bash
PROJECT=arl-dtpr-dev-cust-segmen
PNUM=<PROJECT_NUMBER>
gcloud config set project $PROJECT

gcloud projects get-iam-policy $PROJECT --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount AND NOT bindings.members:gcp-sa-" \
  --format="table(bindings.role, bindings.members)"
```
Anotar que la cuenta de Compute aparece con `roles/editor` y `sa-cloudfunction-segmen` con `roles/bigquery.dataEditor`.

### 3.3. Variables
```bash
PROJECT=arl-dtpr-dev-cust-segmen
PNUM=<PROJECT_NUMBER>
DS=std_arl_all_randomuser
SA_SQ=sa-scheduledquery-segmen@$PROJECT.iam.gserviceaccount.com
SA_BUILD=sa-cloudbuild-segmen@$PROJECT.iam.gserviceaccount.com
SA_CF=sa-cloudfunction-segmen@$PROJECT.iam.gserviceaccount.com
CFG_ENROLL=<ID_SQ_SYNTHETIC_ENROLLMENT>
CFG_SEGMENT=<ID_SQ_EVALUATE_CUSTOMER_SEGMENT>
gcloud config set project $PROJECT
```

---

## 4. Fase A — Crear y otorgar (no rompe nada)

### 4.1. Crear las 2 cuentas
```bash
gcloud iam service-accounts create sa-scheduledquery-segmen \
  --display-name="Runtime identity for the Scheduled Queries of cust-segmen"

gcloud iam service-accounts create sa-cloudbuild-segmen \
  --display-name="Build identity for Cloud Run and Cloud Functions source deploys"
```

### 4.2. Permisos de proyecto
```bash
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_SQ" --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_BUILD" --role="roles/run.builder"
```

### 4.3. Permisos por dataset (DCL)
Los `GRANT` son SQL: **no se pegan en la terminal**. Se ejecutan con `bq query` (el `'EOF'` entre comillas evita que bash interprete los backticks) o en BigQuery Studio.
```bash
bq query --use_legacy_sql=false --project_id=$PROJECT <<'EOF'
GRANT `roles/bigquery.dataEditor` ON SCHEMA `arl-dtpr-dev-cust-segmen.std_arl_all_randomuser`
  TO "serviceAccount:sa-scheduledquery-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com";

GRANT `roles/bigquery.dataEditor` ON SCHEMA `arl-dtpr-dev-cust-segmen.std_arl_all_randomuser`
  TO "serviceAccount:sa-cloudfunction-segmen@arl-dtpr-dev-cust-segmen.iam.gserviceaccount.com";
EOF
```
Verificar (deben aparecer las 2 cuentas como `WRITER`):
```bash
bq show --format=prettyjson $PROJECT:$DS | grep -B2 -A2 "sa-"
```

---

## 5. Fase B — Cambios de comportamiento (probar después de cada uno)

### 5.1. Las 2 Scheduled Queries con su propia identidad (por la consola)
`bq update --service_account_name` no es fiable: reporta éxito sin aplicar el cambio. Se hace en la consola, **una vez por cada query**:

BigQuery → **Scheduled queries** → `sq_generate_synthetic_enrollment` → **Edit** → **Schedule** → **Update scheduled query**:
1. En **Schedule options**, poner **Repeat frequency = On-demand**. (Si se guarda sin revisarlo, el panel activa `every 1 hours` y la query empieza a correr sola.)
2. En **Service account**, elegir `sa-scheduledquery-segmen` ("Build identity…" y "Runtime identity…" se parecen: verificar el correo completo).
3. **Save**.

Repetir con `sq_evaluate_customer_segment`.

Comprobar que ninguna quedó con horario:
```bash
for CFG in $CFG_ENROLL $CFG_SEGMENT; do
  echo "== $CFG"
  bq show --format=prettyjson --transfer_config projects/$PNUM/locations/us/transferConfigs/$CFG \
    | grep -E '"(schedule|nextRunTime|disabled)"'
done
```
No debe imprimir nada. En la lista de Scheduled queries, **Schedule** debe decir `None`.

**Prueba:** esperar 2 minutos y ejecutar `orquestador-cust-segmen` con **Execute**. Debe terminar con `enrollment_query_final_state: SUCCEEDED` y `segment_query_final_state: SUCCEEDED`. Confirmar la identidad de los jobs:
```bash
bq query --use_legacy_sql=false --project_id=$PROJECT \
  "SELECT job_id, user_email, creation_time FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE job_id LIKE 'scheduled_query_%' ORDER BY creation_time DESC LIMIT 4"
```
`user_email` debe ser `sa-scheduledquery-segmen@…`.

### 5.2. Cloud Build con su propia identidad
**Cloud Run** (mismo comando de despliegue de la documentación + `--build-service-account`). Desde la carpeta con el código (verificar antes con `unzip -l` que el zip sea el de `cr-registration-ingest`):
```bash
gcloud run deploy cr-registration-ingest \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated \
  --service-account=sa-cloudrun-segmen@$PROJECT.iam.gserviceaccount.com \
  --build-service-account=projects/$PROJECT/serviceAccounts/sa-cloudbuild-segmen@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,SERVICE_NAME=cr-registration-ingest,RANDOM_USER_URL=https://randomuser.me/api/,BATCH_SIZE=5,PUBSUB_TOPIC=customer-registered
```
**Cloud Functions** — probar con la que no depende de un webhook, `cf-route-customer-decision`:
```bash
gcloud functions deploy cf-route-customer-decision \
  --gen2 --runtime=python312 --region=us-central1 --source=. \
  --entry-point=main --trigger-http \
  --service-account=$SA_CF \
  --build-service-account=projects/$PROJECT/serviceAccounts/sa-cloudbuild-segmen@$PROJECT.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars=PROJECT_ID=arl-dtpr-dev-cust-segmen,REGION=us-central1,SERVICE_NAME=cf-route-customer-decision,BQ_DATASET=std_arl_all_randomuser,BQ_TABLE=trx_customer_segment_decision,OUTPUT_PUBSUB_TOPIC=customer-segment-notification
```
> **Verificado:** `roles/run.builder` alcanza para los builds de Cloud Functions gen2 en este proyecto. El deploy de `cf-route-customer-decision` con `--build-service-account` terminó bien y su `buildConfig.serviceAccount` es `sa-cloudbuild-segmen`. Si en otro proyecto el build de una función falla con `does not have permission to write logs`, `artifactregistry` o `storage`, pegar el mensaje exacto antes de agregar roles.

Después de cada deploy, **redesplegar una función no restablece sus permisos `run.invoker`** (viven sobre el servicio, no sobre la revisión), pero conviene comprobarlo con la prueba E2E.

Verificar la cuenta usada por cada build:
```bash
gcloud builds list --region=us-central1 --limit=3 --format="table(id.slice(0:8), status, createTime, serviceAccount)"
```
Las cuentas de los builds nuevos deben ser `sa-cloudbuild-segmen`. Los demás componentes (`cf-enrich-and-notify`, `cf-forward-to-marketing-platform`, `cf-notify-segment-consumer`) usarán la cuenta nueva en su próximo despliegue: indicar siempre `--build-service-account`.

### 5.3. Bajar el `dataEditor` de `sa-cloudfunction-segmen` de proyecto a dataset
El `GRANT` de 4.3 ya dio el acceso por dataset. Retirar el de proyecto:
```bash
gcloud projects remove-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_CF" --role="roles/bigquery.dataEditor"
```
Verificar (no debe listar `bigquery.dataEditor` para esa cuenta; `jobUser` sí debe seguir):
```bash
gcloud projects get-iam-policy $PROJECT --flatten="bindings[].members" \
  --filter="bindings.members:sa-cloudfunction-segmen" --format="table(bindings.role)"
```
**Prueba:** esperar 2 minutos y ejecutar el Workflow con **Execute**. Debe terminar en `Succeeded`, y en los logs de `cf-enrich-and-notify` debe aparecer `FIN cf-enrich-and-notify OK` (inserta en BigQuery con el permiso por dataset).

---

## 6. Fase C — Retirar `roles/editor` de la cuenta de Compute

Solo cuando las pruebas de la Fase B pasaron.
```bash
gcloud projects remove-iam-policy-binding $PROJECT \
  --member="serviceAccount:$PNUM-compute@developer.gserviceaccount.com" \
  --role="roles/editor"
```
Verificar (no debe salir ningún rol):
```bash
gcloud projects get-iam-policy $PROJECT --flatten="bindings[].members" \
  --filter="bindings.members:$PNUM-compute@developer.gserviceaccount.com" \
  --format="table(bindings.role)"
```
**Prueba final** (esperar 2 minutos): Execute del Workflow + un redespliegue de `cr-registration-ingest` y de `cf-route-customer-decision` con `--build-service-account`.

**Rollback** (solo si hace falta volver atrás mientras se investiga):
```bash
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$PNUM-compute@developer.gserviceaccount.com" --role="roles/editor"
```

---

## 7. Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `GRANT: command not found` | Los `GRANT` se pegaron en la terminal | Ejecutarlos con `bq query <<'EOF'` o en BigQuery Studio |
| Scheduled Query `FAILED` con `Access Denied ... dataset` o `bigquery.jobs.create` | Falta el `GRANT` de 4.3 o `jobUser`, o IAM aún no propaga | Revisar 4.2 y 4.3, esperar 2 min y reintentar |
| Una Scheduled Query empieza a correr sola cada hora | Se guardó el panel con `Repeat frequency = Hours` | Editar → **On-demand** → verificar el Service account → Save |
| Workflow con `403` en `startManualRuns` tras cambiar la cuenta de las queries | El Workflow dispara una transferencia que corre con otra cuenta | Dar `roles/iam.serviceAccountUser` a `sa-workflow-segmen` **sobre** `sa-scheduledquery-segmen` (no a nivel proyecto) |
| Build falla con `does not have permission to write logs` / `artifactregistry` / `storage` | `run.builder` no basta para ese tipo de build, o no propagó | Esperar 2 min; si persiste, pegar el mensaje exacto |
| `cf-enrich-and-notify` con error de BigQuery tras el paso 5.3 | Falta el `GRANT` por dataset de 4.3 | Verificar con `bq show`; repetir el `GRANT` |
| `429 Request limit exceeded` en un webhook | Tope de 50 requests de webhook.site | Generar una URL nueva y actualizarla con `gcloud run services update ... --update-env-vars` |

---

## 8. Validación final (solo lectura)

```bash
PROJECT=arl-dtpr-dev-cust-segmen
PNUM=<PROJECT_NUMBER>
gcloud config set project $PROJECT

echo "===== 1. IAM a nivel proyecto ====="
gcloud projects get-iam-policy $PROJECT --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount AND NOT bindings.members:gcp-sa-" \
  --format="table(bindings.role, bindings.members)"

echo "===== 2. Identidad de las Scheduled Queries (jobs reales) ====="
bq query --use_legacy_sql=false --project_id=$PROJECT \
  "SELECT job_id, user_email, creation_time FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE job_id LIKE 'scheduled_query_%' ORDER BY creation_time DESC LIMIT 4"

echo "===== 3. Permisos del dataset ====="
bq show --format=prettyjson $PROJECT:std_arl_all_randomuser | grep -B2 -A2 "sa-"

echo "===== 4. Últimos builds (cuenta usada) ====="
gcloud builds list --region=us-central1 --limit=3 --format="table(status, createTime, serviceAccount)"

echo "===== 5. Las 2 Scheduled Queries sin horario ====="
for CFG in <ID_SQ_SYNTHETIC_ENROLLMENT> <ID_SQ_EVALUATE_CUSTOMER_SEGMENT>; do
  echo "-- $CFG"; bq show --format=prettyjson --transfer_config projects/$PNUM/locations/us/transferConfigs/$CFG \
    | grep -E '"(schedule|nextRunTime|disabled)"'
done

echo "===== 6. Última ejecución del Workflow ====="
gcloud workflows executions list orquestador-cust-segmen --location=us-central1 --limit=1
```
Esperado: la cuenta de Compute sin ningún rol; `sa-cloudfunction-segmen` sin `bigquery.dataEditor` de proyecto; `sa-scheduledquery-segmen` con `jobUser`; `sa-cloudbuild-segmen` con `run.builder`; jobs de las queries ejecutados por `sa-scheduledquery-segmen`; dataset con `sa-scheduledquery-segmen` y `sa-cloudfunction-segmen` como `WRITER`; builds recientes con `sa-cloudbuild-segmen`; punto 5 sin salida; Workflow en `SUCCEEDED`.

---

## 8.1. Resultado de la aplicación (24/09/2026)

| Paso | Resultado |
|---|---|
| Fase A: 2 cuentas nuevas y sus permisos | Hecho; `sa-cloudfunction-segmen` y `sa-scheduledquery-segmen` como `WRITER` en `std_arl_all_randomuser` |
| 5.1: identidad de las 2 Scheduled Queries | Hecho y verificado: los jobs del Workflow los ejecutó `sa-scheduledquery-segmen`; ninguna query quedó con horario |
| 5.2: builds con `sa-cloudbuild-segmen` | Hecho: `cr-registration-ingest` y `cf-route-customer-decision` |
| 5.3: `dataEditor` de proyecto retirado a `sa-cloudfunction-segmen` | Hecho: `cf-enrich-and-notify` siguió insertando en `trx_customer_notification` |
| Fase C: `roles/editor` retirado a la cuenta de Compute | Hecho: Workflow en `Succeeded` y dos redespliegues en `SUCCESS` con `sa-cloudbuild-segmen` |

**Hallazgos durante la aplicación**
- Las 2 queries no tenían la misma identidad: `sq_generate_synthetic_enrollment` usaba la cuenta de Compute y `sq_evaluate_customer_segment` **no tenía cuenta de servicio** (corría con las credenciales del usuario). El job del 21/09 de esta última figuraba con la cuenta del usuario de la consola.
- La cuenta default de App Engine (`arl-dtpr-dev-cust-segmen@appspot.gserviceaccount.com`) también tenía `roles/editor` y ningún componente la usa. **Se le retiró igual que a Compute** y se verificó: el Workflow (ejecución `83594da4-a258-4637-885d-53ff6fefb146`) terminó en `Succeeded` y `cf-enrich-and-notify` siguió procesando sin errores (22:34:44 UTC). En Weather esta cuenta no existía.
- **(Corregido el 25/09/2026)** `cf-route-customer-decision` notificaba todos los `special_program` con fecha de hoy en cada ejecución (`routed` crecía entre corridas: 6, 10, 13). Ahora filtra por la hora de inicio de la evaluación de cada corrida (`routed: 3` en la corrida de verificación).
- **(Actualizado el 25/09/2026)** `BATCH_SIZE` está en 30, con URLs de webhook nuevas para marketing y para el consumidor.
