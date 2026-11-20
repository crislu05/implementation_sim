"""Test runner. Runs as a short-lived subprocess, isolated from the server.

Reads a JSON job on stdin, writes a JSON report on stdout. Nothing else is
printed to stdout -- user `print()` output is captured per case and returned
inside the report, because people debug with prints and need to see them.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import io
import json
import math
import os
import signal
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr

MAX_REPR = 2000
MAX_STDOUT = 8000


class CaseTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise CaseTimeout()


# ---------- value helpers ----------

def short(text: str, limit: int = MAX_REPR) -> str:
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} more chars]"


def jsonable(value):
    """Best-effort JSON view of a value, so the UI can render structure."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return repr(value)
        return value
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(repr(v) for v in value)
    return repr(value)


def deep_equal(a, b) -> bool:
    """Strict structural equality. True != 1, and tuples match lists."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(deep_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return float(a) == float(b)
        return False
    return a == b


def deep_approx(a, b, tol: float) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(deep_approx(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(deep_approx(a[k], b[k], tol) for k in a)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return deep_equal(a, b)


def _sort_key(v):
    return (type(v).__name__, repr(v))


def compare(expected, actual, match: str, tol: float) -> bool:
    if match == "approx":
        return deep_approx(expected, actual, tol)
    if match == "unordered":
        if not isinstance(actual, (list, tuple, set)):
            return False
        try:
            return deep_equal(
                sorted(list(expected), key=_sort_key), sorted(list(actual), key=_sort_key)
            )
        except TypeError:
            return False
    return deep_equal(expected, actual)


def resolve_args(args, given: dict):
    """Replace "$given.name" markers with the live fixture objects."""
    if isinstance(args, str) and args.startswith("$given."):
        return given[args.split(".", 1)[1]]
    if isinstance(args, list):
        return [resolve_args(a, given) for a in args]
    if isinstance(args, dict):
        return {k: resolve_args(v, given) for k, v in args.items()}
    return args


# ---------- module loading ----------

def load_solution(path: str):
    spec = importlib.util.spec_from_file_location("user_solution", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["user_solution"] = module
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        spec.loader.exec_module(module)
    return module, short(buf.getvalue(), MAX_STDOUT)


def is_stub(func, source_path: str) -> bool:
    """True when the body is only a docstring, `pass`, `...` and comments."""
    try:
        tree = ast.parse(open(source_path).read())
    except Exception:
        return False
    name = getattr(func, "__name__", None)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body = body[1:]
            return all(
                isinstance(n, ast.Pass)
                or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                    and n.value.value is Ellipsis)
                for n in body
            ) if body is not None else True
    return False


def user_traceback(exc: BaseException, solution_path: str) -> dict:
    tb = exc.__traceback__
    frames = traceback.extract_tb(tb)
    own = [f for f in frames if os.path.abspath(f.filename) == os.path.abspath(solution_path)]
    shown = own or frames[1:]
    lines = [f"  {f.name}, line {f.lineno}:  {(f.line or '').strip()}" for f in shown]
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "frames": lines,
        "line": own[-1].lineno if own else None,
        "text": short("".join(traceback.format_exception(type(exc), exc, tb))),
    }


# ---------- running ----------

def run_case(func, case: dict, kind: str, mutates: list[str], solution_path: str,
             timeout_s: float) -> dict:
    given = copy.deepcopy(case.get("given", {}))
    args = resolve_args(copy.deepcopy(case.get("args", [])), given)
    expect = case.get("expect", {})
    match = expect.get("match", "equal")
    tol = float(expect.get("tol", 1e-6))

    out = io.StringIO()
    started = time.perf_counter()
    raised: BaseException | None = None
    returned = None
    timed_out = False

    signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        with redirect_stdout(out), redirect_stderr(out):
            returned = func(*args)
    except CaseTimeout:
        timed_out = True
    except BaseException as exc:  # noqa: BLE001 - user code may raise anything
        raised = exc
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    result = {
        "case_id": case["id"],
        "why": case.get("why", ""),
        "tags": case.get("tags", []),
        "visible": case.get("visible", True),
        "call": f"{func.__name__}({', '.join(short(repr(a), 160) for a in args)})",
        "duration_ms": duration_ms,
        "stdout": short(out.getvalue(), MAX_STDOUT),
        "checks": [],
    }

    if timed_out:
        result["status"] = "timeout"
        result["error"] = {"type": "Timeout", "message": f"exceeded {timeout_s}s", "frames": []}
        return result

    if match == "raises":
        wanted = expect.get("raises")
        ok = raised is not None and type(raised).__name__ == wanted
        result["status"] = "pass" if ok else "fail"
        result["checks"].append({
            "label": "raises",
            "ok": ok,
            "expected": wanted,
            "actual": type(raised).__name__ if raised else "nothing raised",
        })
        return result

    if raised is not None:
        result["status"] = "error"
        result["error"] = user_traceback(raised, solution_path)
        if "returns" in expect:
            result["checks"].append({
                "label": "returns", "ok": False,
                "expected": jsonable(expect["returns"]),
                "actual": f"raised {type(raised).__name__}",
            })
        return result

    ok = True
    if "returns" in expect or match == "is_none":
        if match == "is_none":
            good = returned is None
            expected_view = None
        else:
            good = compare(expect["returns"], returned, match, tol)
            expected_view = jsonable(expect["returns"])
        ok = ok and good
        result["checks"].append({
            "label": "returns",
            "ok": good,
            "expected": expected_view,
            "expected_repr": short(repr(expect.get("returns"))),
            "actual": jsonable(returned),
            "actual_repr": short(repr(returned)),
            "match": match,
        })

    if kind == "stateful" and isinstance(expect.get("state"), dict):
        for name, want in expect["state"].items():
            got = given.get(name)
            good = compare(want, got, match if match == "approx" else "equal", tol)
            ok = ok and good
            result["checks"].append({
                "label": f"state: {name}",
                "ok": good,
                "expected": jsonable(want),
                "expected_repr": short(repr(want)),
                "actual": jsonable(got),
                "actual_repr": short(repr(got)),
                "match": "equal",
            })

    result["status"] = "pass" if ok else "fail"
    return result


def run_target(module, target: dict, solution_path: str, timeout_s: float) -> dict:
    name = target["target"]
    report = {
        "target": name,
        "kind": target.get("kind", "pure"),
        "signature": target.get("signature", ""),
        "results": [],
    }
    func = getattr(module, name, None)
    if func is None or not callable(func):
        report["status"] = "not_implemented"
        report["message"] = (
            f"'{name}' is not defined in your solution (or is not a function). "
            "Keep the name and signature from the spec -- the tests call it directly."
        )
        return report
    if is_stub(func, solution_path):
        report["status"] = "not_implemented"
        report["message"] = f"'{name}' has an empty body -- nothing to test yet."
        return report

    for case in target.get("cases", []):
        report["results"].append(
            run_case(func, case, target.get("kind", "pure"), target.get("mutates", []),
                     solution_path, timeout_s)
        )
    statuses = [r["status"] for r in report["results"]]
    report["status"] = "pass" if statuses and all(s == "pass" for s in statuses) else "fail"
    report["passed"] = sum(1 for s in statuses if s == "pass")
    report["total"] = len(statuses)
    return report


def main() -> None:
    job = json.loads(sys.stdin.read())
    solution_path = job["solution_path"]
    timeout_s = float(job.get("case_timeout_s", 2.0))
    sys.setrecursionlimit(int(job.get("recursion_limit", 3000)))

    report: dict = {"targets": []}
    try:
        module, import_output = load_solution(solution_path)
    except BaseException as exc:  # noqa: BLE001
        report["import_error"] = user_traceback(exc, solution_path)
        print(json.dumps(report))
        return
    report["import_output"] = import_output

    for target in job["targets"]:
        report["targets"].append(run_target(module, target, solution_path, timeout_s))

    print(json.dumps(report))


if __name__ == "__main__":
    main()
