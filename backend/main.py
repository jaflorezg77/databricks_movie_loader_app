import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from databricks.sdk import WorkspaceClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("movie-loader")

JOB_ID_ENV = "JOB_ID"
TABLE_NAME = "demo_catalog.silver.movie"

app = FastAPI(title="Databricks Movie Loader API", version="1.0.0")

# Only needed for local development if the frontend is served by Vite.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workspace_client = WorkspaceClient()


def get_job_id() -> int:
    value = os.getenv(JOB_ID_ENV)
    if not value:
        raise RuntimeError(
            "JOB_ID no está configurado. Agrega el Lakeflow Job "
            "como recurso de la Databricks App y referencia "
            "'valueFrom: movie-load-job' en app.yaml."
        )
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError("JOB_ID debe ser numérico.") from exc


def get_attr(obj: Any, name: str, default=None):
    if obj is None:
        return default
    return getattr(obj, name, default)


def normalize_status(run) -> tuple[str, str]:
    run_state = get_attr(run, "state")
    lifecycle = get_attr(run_state, "life_cycle_state", None)
    result_state = get_attr(run_state, "result_state", None)
    state_message = get_attr(run_state, "state_message", "")

    if result_state == "SUCCESS":
        return "SUCCESS", state_message

    if result_state in {
        "FAILED",
        "TIMEDOUT",
        "CANCELED",
        "MAXIMUM_CONCURRENT_RUNS_REACHED",
        "UPSTREAM_CANCELED",
        "UPSTREAM_FAILED",
        "EXCLUDED",
        "SUCCESS_WITH_FAILURES",
        "DISABLED",
    }:
        return "FAILED", state_message or str(result_state)

    if lifecycle:
        return lifecycle, state_message

    return "PENDING", state_message


def parse_notebook_output(output: Any) -> dict:
    if not output:
        return {}

    notebook_output = get_attr(output, "notebook_output")
    if notebook_output is None:
        return {}

    result = get_attr(notebook_output, "result", None)

    if not result:
        return {}

    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, json.JSONDecodeError):
        pass

    return {"message": result}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs/run")
def run_job():
    try:
        job_id = get_job_id()

        run = workspace_client.jobs.run_now(
            job_id=job_id
        )

        run_id = get_attr(run, "run_id")

        if not run_id:
            raise RuntimeError("Databricks no devolvió un run_id.")

        logger.info("Job iniciado. job_id=%s run_id=%s", job_id, run_id)

        return {
            "job_id": job_id,
            "run_id": run_id,
            "status": "PENDING",
        }

    except Exception as exc:
        logger.exception("Error iniciando Job")
        raise HTTPException(
            status_code=500,
            detail=f"No fue posible iniciar el Job: {exc}",
        ) from exc


@app.get("/api/runs/{run_id}")
def get_run_status(run_id: int):
    try:
        run = workspace_client.jobs.get_run(run_id=run_id)

        status, state_message = normalize_status(run)
        terminal = status in {
            "SUCCESS",
            "FAILED",
            "CANCELED",
            "TIMEDOUT",
            "INTERNAL_ERROR",
        }

        run_page_url = get_attr(run, "run_page_url", "")

        response = {
            "run_id": run_id,
            "job_id": get_attr(run, "job_id"),
            "status": status,
            "terminal": terminal,
            "message": state_message,
            "run_page_url": run_page_url,
        }

        if terminal:
            tasks = get_attr(run, "tasks", []) or []

            # For a notebook task, get-output expects the task run_id.
            task_run_id = None
            if tasks:
                task_run_id = get_attr(tasks[0], "run_id")

            if status == "SUCCESS" and task_run_id:
                try:
                    output = workspace_client.jobs.get_run_output(
                        run_id=task_run_id
                    )
                    response["result"] = parse_notebook_output(output)
                except Exception as exc:
                    logger.warning(
                        "No fue posible recuperar el output del Notebook: %s",
                        exc,
                    )

        return response

    except Exception as exc:
        logger.exception("Error consultando run_id=%s", run_id)
        raise HTTPException(
            status_code=500,
            detail=f"No fue posible consultar la ejecución: {exc}",
        ) from exc


# Serve the compiled Vue application.
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=DIST_DIR, html=True),
        name="frontend",
    )
