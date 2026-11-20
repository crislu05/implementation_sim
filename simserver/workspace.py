"""Workspaces: every keystroke and every run lands on local disk.

    workspaces/<bundle-id>/<attempt-id>/
        solution.py            the file the editor owns (autosaved)
        .sim/state.json        per-unit status, timer, last run
        .sim/runs/<id>.json    append-only run history
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from .schema import Bundle

STATE_DIR = ".sim"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Attempt:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.id = self.root.name
        self.bundle_id = self.root.parent.name

    # ---------- paths ----------
    @property
    def solution_path(self) -> Path:
        return self.root / "solution.py"

    @property
    def state_path(self) -> Path:
        return self.root / STATE_DIR / "state.json"

    @property
    def last_results_path(self) -> Path:
        return self.root / STATE_DIR / "last_results.json"

    @property
    def runs_dir(self) -> Path:
        return self.root / STATE_DIR / "runs"

    # ---------- state ----------
    def state(self) -> dict:
        if self.state_path.is_file():
            return json.loads(self.state_path.read_text())
        return {}

    def write_state(self, **updates) -> dict:
        state = self.state()
        state.update(updates)
        state["updated_at"] = _now_iso()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2))
        return state

    def last_results(self) -> dict:
        """The most recent result for each target, whichever run produced it.

        A function that passed two runs ago is still a function that passed --
        the panel should say so rather than claiming it was never run.
        """
        if self.last_results_path.is_file():
            return json.loads(self.last_results_path.read_text())
        return {}

    # ---------- code ----------
    def code_hash(self) -> str:
        """Identifies the exact file a status was produced from."""
        return hashlib.sha1(self.code().encode()).hexdigest()[:12]

    def code(self) -> str:
        return self.solution_path.read_text() if self.solution_path.is_file() else ""

    def save_code(self, code: str) -> dict:
        self.solution_path.write_text(code)
        return self.write_state(bytes=len(code.encode()))

    # ---------- runs ----------
    def record_run(self, selection: str, report: dict, summary: dict) -> dict:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{selection.replace('/', '_')}"
        entry = {
            "run_id": run_id,
            "at": _now_iso(),
            "selection": selection,
            "summary": summary,
            "report": report,
        }
        (self.runs_dir / f"{run_id}.json").write_text(json.dumps(entry, indent=2))

        code_hash = self.code_hash()
        latest = self.last_results()
        for target in report.get("targets", []):
            latest[target["target"]] = {
                **target, "at": entry["at"], "run_id": run_id, "code_hash": code_hash,
            }
        self.last_results_path.write_text(json.dumps(latest, indent=2))

        status = self.state().get("unit_status", {})
        for target in report.get("targets", []):
            status[target["target"]] = {
                "status": target.get("status", "fail"),
                "passed": target.get("passed", 0),
                "total": target.get("total", 0),
                "at": entry["at"],
                "code_hash": code_hash,
            }
        self.write_state(unit_status=status, last_run_id=run_id, code_hash=code_hash)
        return entry

    def history(self, limit: int = 50) -> list[dict]:
        if not self.runs_dir.is_dir():
            return []
        files = sorted(self.runs_dir.glob("*.json"), reverse=True)[:limit]
        out = []
        for f in files:
            try:
                e = json.loads(f.read_text())
            except ValueError:
                continue
            out.append({"run_id": e["run_id"], "at": e["at"],
                        "selection": e["selection"], "summary": e["summary"]})
        return out

    def run_detail(self, run_id: str) -> dict | None:
        path = self.runs_dir / f"{run_id}.json"
        return json.loads(path.read_text()) if path.is_file() else None

    def info(self) -> dict:
        state = self.state()
        return {
            "attempt_id": self.id,
            "bundle_id": self.bundle_id,
            "path": str(self.root),
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "unit_status": state.get("unit_status", {}),
            "code_hash": self.code_hash(),
            "elapsed_seconds": state.get("elapsed_seconds", 0),
        }


class Workspaces:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def bundle_dir(self, bundle_id: str) -> Path:
        d = self.root / bundle_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_attempts(self, bundle_id: str) -> list[dict]:
        d = self.bundle_dir(bundle_id)
        return [Attempt(p).info() for p in sorted(d.iterdir(), reverse=True) if p.is_dir()]

    def get(self, bundle_id: str, attempt_id: str) -> Attempt | None:
        p = self.bundle_dir(bundle_id) / attempt_id
        return Attempt(p) if p.is_dir() else None

    def create(self, bundle: Bundle) -> Attempt:
        attempt_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        path = self.bundle_dir(bundle.id) / attempt_id
        suffix = 1
        while path.exists():
            suffix += 1
            path = self.bundle_dir(bundle.id) / f"{attempt_id}-{suffix}"
        (path / STATE_DIR / "runs").mkdir(parents=True)
        attempt = Attempt(path)
        attempt.solution_path.write_text(bundle.skeleton_code)
        attempt.write_state(created_at=_now_iso(), bundle_id=bundle.id,
                            bundle_title=bundle.title, unit_status={}, elapsed_seconds=0)
        return attempt

    def latest_or_create(self, bundle: Bundle) -> Attempt:
        attempts = self.list_attempts(bundle.id)
        if attempts:
            existing = self.get(bundle.id, attempts[0]["attempt_id"])
            if existing:
                return existing
        return self.create(bundle)
