"""FastAPI app. Local-only service: bundle library, workspaces, test runs."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import execute
from .library import Library
from .schema import BundleError
from .workspace import Workspaces

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIM_HOME = Path(os.environ.get("SIM_HOME", PROJECT_ROOT / "data")).expanduser()
STATIC_DIR = Path(__file__).resolve().parent / "static"

library = Library(SIM_HOME / "bundles")
workspaces = Workspaces(SIM_HOME / "workspaces")

app = FastAPI(title="implementation_sim")


class CodePayload(BaseModel):
    code: str


class RunPayload(BaseModel):
    selection: str = "all"
    code: str | None = None


class HeartbeatPayload(BaseModel):
    elapsed_seconds: int


class ImportPathPayload(BaseModel):
    path: str


def _bundle(bundle_id: str):
    try:
        return library.load(bundle_id)
    except BundleError as exc:
        raise HTTPException(422, {"problems": exc.problems})
    except FileNotFoundError:
        raise HTTPException(404, f"no bundle '{bundle_id}'")


def _attempt(bundle_id: str, attempt_id: str):
    attempt = workspaces.get(bundle_id, attempt_id)
    if attempt is None:
        raise HTTPException(404, f"no attempt '{attempt_id}'")
    return attempt


# ---------- library ----------

@app.get("/api/bundles")
def list_bundles():
    return {"bundles": library.list(), "home": str(SIM_HOME)}


@app.post("/api/bundles/import")
async def import_bundle(file: UploadFile = File(...)):
    try:
        bundle, summary = library.import_zip(await file.read())
    except BundleError as exc:
        return JSONResponse(status_code=422, content={"problems": exc.problems})
    return {"bundle": bundle.to_dict(include_cases=False), "verified": summary}


@app.post("/api/bundles/import-path")
def import_bundle_path(payload: ImportPathPayload):
    src = Path(payload.path).expanduser()
    if not src.is_dir():
        return JSONResponse(status_code=422, content={"problems": [f"not a directory: {src}"]})
    try:
        bundle, summary = library.import_dir(src)
    except BundleError as exc:
        return JSONResponse(status_code=422, content={"problems": exc.problems})
    return {"bundle": bundle.to_dict(include_cases=False), "verified": summary}


@app.get("/api/bundles/{bundle_id}")
def get_bundle(bundle_id: str):
    bundle = _bundle(bundle_id)
    data = bundle.to_dict(include_cases=True)
    data["docs"] = [
        {**d, "markdown": (bundle.root / d["file"]).read_text()} for d in bundle.docs
    ]
    data["skeleton"] = bundle.skeleton_code
    return data


@app.get("/api/bundles/{bundle_id}/reference")
def get_reference(bundle_id: str):
    return {"code": _bundle(bundle_id).reference_code}


# ---------- attempts ----------

@app.get("/api/bundles/{bundle_id}/attempts")
def list_attempts(bundle_id: str):
    _bundle(bundle_id)
    return {"attempts": workspaces.list_attempts(bundle_id)}


@app.post("/api/bundles/{bundle_id}/attempts")
def create_attempt(bundle_id: str):
    attempt = workspaces.create(_bundle(bundle_id))
    return {**attempt.info(), "code": attempt.code()}


@app.get("/api/bundles/{bundle_id}/attempts/latest")
def latest_attempt(bundle_id: str):
    attempt = workspaces.latest_or_create(_bundle(bundle_id))
    return {**attempt.info(), "code": attempt.code(), "history": attempt.history(),
            "last_results": attempt.last_results()}


@app.get("/api/bundles/{bundle_id}/attempts/{attempt_id}")
def get_attempt(bundle_id: str, attempt_id: str):
    attempt = _attempt(bundle_id, attempt_id)
    return {**attempt.info(), "code": attempt.code(), "history": attempt.history(),
            "last_results": attempt.last_results()}


@app.put("/api/bundles/{bundle_id}/attempts/{attempt_id}/code")
def save_code(bundle_id: str, attempt_id: str, payload: CodePayload):
    attempt = _attempt(bundle_id, attempt_id)
    attempt.save_code(payload.code)
    return {"saved_at": attempt.state().get("updated_at"), "path": str(attempt.solution_path)}


@app.post("/api/bundles/{bundle_id}/attempts/{attempt_id}/heartbeat")
def heartbeat(bundle_id: str, attempt_id: str, payload: HeartbeatPayload):
    attempt = _attempt(bundle_id, attempt_id)
    attempt.write_state(elapsed_seconds=payload.elapsed_seconds)
    return {"ok": True}


@app.post("/api/bundles/{bundle_id}/attempts/{attempt_id}/run")
def run_tests(bundle_id: str, attempt_id: str, payload: RunPayload):
    bundle = _bundle(bundle_id)
    attempt = _attempt(bundle_id, attempt_id)
    if payload.code is not None:
        attempt.save_code(payload.code)
    try:
        targets = execute.build_targets(bundle, payload.selection)
    except KeyError:
        raise HTTPException(404, f"no unit '{payload.selection}'")
    report = execute.run(attempt.solution_path, targets)
    summary = execute.summarize(report)
    entry = attempt.record_run(payload.selection, report, summary)
    return {
        "run_id": entry["run_id"], "at": entry["at"], "selection": payload.selection,
        "summary": summary, "report": report,
        "unit_status": attempt.state().get("unit_status", {}),
        "code_hash": attempt.code_hash(),
        "last_results": attempt.last_results(),
    }


@app.get("/api/bundles/{bundle_id}/attempts/{attempt_id}/runs")
def list_runs(bundle_id: str, attempt_id: str):
    return {"history": _attempt(bundle_id, attempt_id).history()}


@app.get("/api/bundles/{bundle_id}/attempts/{attempt_id}/runs/{run_id}")
def get_run(bundle_id: str, attempt_id: str, run_id: str):
    detail = _attempt(bundle_id, attempt_id).run_detail(run_id)
    if detail is None:
        raise HTTPException(404, f"no run '{run_id}'")
    return detail


# ---------- static UI ----------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
