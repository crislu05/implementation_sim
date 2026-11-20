"""Server-side orchestration of runner subprocesses."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .schema import Bundle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASE_TIMEOUT_S = 2.0
RUN_OVERHEAD_S = 10.0


def build_targets(bundle: Bundle, selection: str) -> list[dict]:
    """selection: a unit id, 'pipeline', or 'all'."""
    targets: list[dict] = []
    if selection in ("all", "units"):
        chosen = bundle.units
    elif selection == "pipeline":
        chosen = []
    else:
        unit = bundle.unit(selection)
        if unit is None:
            raise KeyError(selection)
        chosen = [unit]

    for unit in chosen:
        targets.append({
            "target": unit.id,
            "kind": unit.kind,
            "mutates": unit.mutates,
            "signature": unit.signature,
            "cases": [c.to_dict() for c in unit.cases],
        })

    if selection in ("all", "pipeline"):
        targets.append({
            "target": bundle.entrypoint,
            "kind": "pure",
            "mutates": [],
            "signature": f"def {bundle.entrypoint}(input)",
            "cases": [c.to_dict() for c in bundle.pipeline_cases],
        })
    return targets


def run(solution_path: Path, targets: list[dict]) -> dict:
    """Run targets against a solution file in a fresh, isolated subprocess."""
    solution_path = Path(solution_path).resolve()
    case_count = sum(len(t["cases"]) for t in targets) or 1
    wall_timeout = RUN_OVERHEAD_S + CASE_TIMEOUT_S * case_count

    job = {
        "solution_path": str(solution_path),
        "targets": targets,
        "case_timeout_s": CASE_TIMEOUT_S,
    }
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "simserver.runner"],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            cwd=str(solution_path.parent),
            env=env,
            timeout=wall_timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "targets": [],
            "fatal": f"The whole run exceeded {wall_timeout:.0f}s and was stopped. "
                     "An infinite loop in one of your functions is the usual cause.",
        }

    if proc.returncode != 0 and not proc.stdout.strip():
        return {
            "targets": [],
            "fatal": "The runner process crashed (this usually means the solution "
                     "crashed the interpreter).",
            "stderr": proc.stderr[-4000:],
        }
    try:
        report = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"targets": [], "fatal": "Could not read the run report.",
                "stderr": (proc.stderr or proc.stdout)[-4000:]}
    if proc.stderr.strip():
        report["stderr"] = proc.stderr[-4000:]
    return report


def summarize(report: dict) -> dict:
    passed = failed = total = 0
    for t in report.get("targets", []):
        for r in t.get("results", []):
            total += 1
            if r["status"] == "pass":
                passed += 1
            else:
                failed += 1
    return {"passed": passed, "failed": failed, "total": total}
