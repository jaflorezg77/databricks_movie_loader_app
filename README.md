# Databricks Movie Loader App

Databricks App con:

- Frontend: Vue 3 + Vuetify
- Build: Vite
- Backend: FastAPI
- Ejecución: Databricks Lakeflow Job
- Autenticación: Databricks Apps App Authorization / OAuth
- Procesamiento: Notebook PySpark

## Arquitectura

Vue/Vuetify -> FastAPI -> Databricks SDK -> Lakeflow Job -> Notebook PySpark
                                                     |
                                                     v
                                        ADLS Bronze -> Unity Catalog Silver

## 1. Requisitos

- Databricks Workspace con Databricks Apps habilitado.
- Unity Catalog.
- Un Lakeflow Job existente con una tarea Notebook.
- Python 3.11+.
- Node.js 22.16+.
- Databricks CLI 0.229+.

## 2. Configurar el Job

Crea un Job, por ejemplo:

LOAD_MOVIE_BRONZE_TO_SILVER

con una única tarea Notebook que ejecute tu Notebook PySpark.

Al final del Notebook puedes devolver un resultado JSON:

```python
import json

total = spark.table("demo_catalog.silver.movie").count()

dbutils.notebook.exit(json.dumps({
    "status": "SUCCESS",
    "table": "demo_catalog.silver.movie",
    "records": total,
    "message": f"Carga completada correctamente. Registros: {total}"
}))
```

## 3. Crear la Databricks App

En Databricks:

Databricks Apps -> Create app -> Custom app

Después agrega el Job como App Resource:

Resource type: Lakeflow Job
Job: LOAD_MOVIE_BRONZE_TO_SILVER
Permission: Can manage run
Resource key: movie-load-job

El app.yaml utiliza esa resource key para recibir el Job ID:

```yaml
env:
  - name: JOB_ID
    valueFrom: movie-load-job
```

No coloques un PAT en el código.

## 4. Ejecutar localmente

Instala dependencias:

```bash
npm install
pip install -r requirements.txt
```

Para el backend local necesitas configurar autenticación Databricks mediante OAuth/U2M y definir:

```bash
DATABRICKS_HOST=https://<tu-workspace>
JOB_ID=<tu-job-id>
```

Construye Vue:

```bash
npm run build
```

Inicia FastAPI:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Abre:

http://localhost:8000

## 5. Desplegar

Puedes sincronizar el directorio con Workspace y desplegarlo como Databricks App:

```bash
databricks sync --watch . /Workspace/Users/<usuario>/databricks_apps/movie-loader
```

Luego selecciona esa carpeta como source de la App y Deploy.

Databricks detectará package.json, instalará Node, ejecutará `npm run build`, instalará requirements.txt y ejecutará app.yaml.

## 6. Flujo de ejecución

1. Usuario pulsa "Ejecutar Notebook".
2. Vue llama POST /api/jobs/run.
3. FastAPI usa WorkspaceClient.jobs.run_now().
4. Databricks devuelve run_id.
5. Vue comienza polling cada 2.5 segundos.
6. FastAPI consulta jobs.get_run().
7. Se muestra RUNNING/PENDING/etc.
8. Cuando termina, se obtiene el task run_id.
9. FastAPI consulta jobs.get_run_output().
10. Vue muestra el resultado devuelto por dbutils.notebook.exit().

## 7. Seguridad

La App usa el service principal administrado por Databricks Apps.

No hardcodear:

- PAT
- client secret
- tokens OAuth
- passwords

El acceso al Job se concede al service principal de la App mediante App Resources.
