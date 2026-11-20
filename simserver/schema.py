"""Bundle schema: the contract a generated bundle must satisfy.

A bundle is a directory. `manifest.json` is the only file the service parses to
bootstrap; everything else is referenced from it. Validation is deliberately
strict and loud: a bundle that cannot be trusted must never reach the editor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

BUNDLE_VERSION = "1.0"

MATCH_MODES = {"equal", "approx", "unordered", "is_none", "raises"}
UNIT_KINDS = {"pure", "stateful"}

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BundleError(Exception):
    """Raised when a bundle is malformed. Message is shown to the user."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


@dataclass
class Case:
    id: str
    args: list
    expect: dict
    given: dict = field(default_factory=dict)
    why: str = ""
    tags: list[str] = field(default_factory=list)
    visible: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "args": self.args,
            "expect": self.expect,
            "given": self.given,
            "why": self.why,
            "tags": self.tags,
            "visible": self.visible,
        }


@dataclass
class Unit:
    id: str
    signature: str
    kind: str = "pure"
    group: str = ""
    order: int = 0
    summary: str = ""
    spec_file: str | None = None
    tests_file: str | None = None
    mutates: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)
    spec_md: str = ""

    def to_dict(self, include_cases: bool = True) -> dict:
        d = {
            "id": self.id,
            "signature": self.signature,
            "kind": self.kind,
            "group": self.group,
            "order": self.order,
            "summary": self.summary,
            "mutates": self.mutates,
            "depends_on": self.depends_on,
            "spec_md": self.spec_md,
            "case_count": len(self.cases),
        }
        if include_cases:
            d["cases"] = [c.to_dict() for c in self.cases]
        return d


@dataclass
class Bundle:
    id: str
    title: str
    root: Path
    entrypoint: str
    language: str
    skeleton: str
    source: str = ""
    estimated_minutes: int = 0
    docs: list[dict] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    pipeline_cases: list[Case] = field(default_factory=list)
    reference: str = "reference/solution.py"

    @property
    def skeleton_code(self) -> str:
        return (self.root / self.skeleton).read_text()

    @property
    def reference_code(self) -> str:
        return (self.root / self.reference).read_text()

    def unit(self, unit_id: str) -> Unit | None:
        return next((u for u in self.units if u.id == unit_id), None)

    def to_dict(self, include_cases: bool = True) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "entrypoint": self.entrypoint,
            "language": self.language,
            "estimated_minutes": self.estimated_minutes,
            "docs": self.docs,
            "units": [u.to_dict(include_cases) for u in self.units],
            "pipeline": {
                "case_count": len(self.pipeline_cases),
                "cases": [c.to_dict() for c in self.pipeline_cases] if include_cases else [],
            },
        }


# ---------- parsing ----------

def _req(obj: dict, key: str, where: str, problems: list[str], typ=None):
    if key not in obj:
        problems.append(f"{where}: missing required field '{key}'")
        return None
    val = obj[key]
    if typ is not None and not isinstance(val, typ):
        problems.append(f"{where}: field '{key}' must be {typ.__name__}, got {type(val).__name__}")
        return None
    return val


def _parse_cases(payload: dict, where: str, expect_target: str, problems: list[str]) -> list[Case]:
    target = _req(payload, "target", where, problems, str)
    if target is not None and target != expect_target:
        problems.append(f"{where}: target '{target}' does not match '{expect_target}'")

    raw_cases = _req(payload, "cases", where, problems, list) or []
    if not raw_cases:
        problems.append(f"{where}: must contain at least one case")

    seen: set[str] = set()
    cases: list[Case] = []
    for i, raw in enumerate(raw_cases):
        loc = f"{where}[case {i}]"
        if not isinstance(raw, dict):
            problems.append(f"{loc}: must be an object")
            continue
        cid = _req(raw, "id", loc, problems, str)
        if cid is None:
            continue
        if cid in seen:
            problems.append(f"{loc}: duplicate case id '{cid}'")
        seen.add(cid)

        args = _req(raw, "args", f"{loc} '{cid}'", problems, list)
        expect = _req(raw, "expect", f"{loc} '{cid}'", problems, dict)
        if args is None or expect is None:
            continue

        match = expect.get("match", "equal")
        if match not in MATCH_MODES:
            problems.append(
                f"{loc} '{cid}': expect.match '{match}' is not one of {sorted(MATCH_MODES)}"
            )
        if match == "raises" and not isinstance(expect.get("raises"), str):
            problems.append(f"{loc} '{cid}': match 'raises' needs an exception name in expect.raises")
        if match not in ("raises", "is_none") and "returns" not in expect and "state" not in expect:
            problems.append(f"{loc} '{cid}': expect needs 'returns' and/or 'state'")
        if match == "is_none" and "returns" in expect:
            problems.append(f"{loc} '{cid}': match 'is_none' must not also set expect.returns")

        given = raw.get("given", {})
        if not isinstance(given, dict):
            problems.append(f"{loc} '{cid}': 'given' must be an object")
            given = {}

        for ref in _refs_in(args):
            name = ref.split(".", 1)[1] if "." in ref else ""
            if name not in given:
                problems.append(f"{loc} '{cid}': args reference '{ref}' but 'given' has no '{name}'")

        state = expect.get("state")
        if state is not None:
            if not isinstance(state, dict):
                problems.append(f"{loc} '{cid}': expect.state must be an object")
            else:
                for name in state:
                    if name not in given:
                        problems.append(
                            f"{loc} '{cid}': expect.state names '{name}' which is not in 'given'"
                        )

        cases.append(
            Case(
                id=cid,
                args=args,
                expect=expect,
                given=given,
                why=raw.get("why", ""),
                tags=raw.get("tags", []),
                visible=bool(raw.get("visible", True)),
            )
        )
    return cases


def _refs_in(value) -> list[str]:
    """Collect every "$given.name" reference appearing anywhere inside args."""
    found: list[str] = []
    if isinstance(value, str) and value.startswith("$given."):
        found.append(value)
    elif isinstance(value, list):
        for v in value:
            found.extend(_refs_in(v))
    elif isinstance(value, dict):
        for v in value.values():
            found.extend(_refs_in(v))
    return found


def _read_json(root: Path, rel: str, where: str, problems: list[str]) -> dict | None:
    path = root / rel
    if not path.is_file():
        problems.append(f"{where}: file not found: {rel}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        problems.append(f"{where}: invalid JSON in {rel}: {exc}")
        return None


def parse_bundle(root: Path) -> Bundle:
    """Parse and structurally validate a bundle directory. Raises BundleError."""
    problems: list[str] = []
    root = Path(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BundleError([f"no manifest.json in {root}"])
    try:
        m = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise BundleError([f"manifest.json is not valid JSON: {exc}"])

    version = m.get("bundle_version")
    if version != BUNDLE_VERSION:
        problems.append(f"manifest: bundle_version must be '{BUNDLE_VERSION}', got {version!r}")

    bid = _req(m, "id", "manifest", problems, str)
    title = _req(m, "title", "manifest", problems, str)
    entrypoint = _req(m, "entrypoint", "manifest", problems, str)
    skeleton = _req(m, "skeleton", "manifest", problems, str)
    language = m.get("language", "python")
    if language != "python":
        problems.append(f"manifest: only language 'python' is supported, got {language!r}")
    if entrypoint and not IDENT.match(entrypoint):
        problems.append(f"manifest: entrypoint {entrypoint!r} is not a valid identifier")
    if skeleton and not (root / skeleton).is_file():
        problems.append(f"manifest: skeleton file not found: {skeleton}")

    reference = m.get("reference", "reference/solution.py")
    if not (root / reference).is_file():
        problems.append(
            f"manifest: reference solution not found: {reference} "
            "(a bundle must ship a reference implementation so its own tests can be verified)"
        )

    docs = m.get("docs", [])
    if not isinstance(docs, list) or not docs:
        problems.append("manifest: 'docs' must be a non-empty list")
        docs = []
    else:
        for i, d in enumerate(docs):
            if not isinstance(d, dict):
                problems.append(f"manifest.docs[{i}]: must be an object")
                continue
            for k in ("id", "title", "file"):
                _req(d, k, f"manifest.docs[{i}]", problems, str)
            f = d.get("file")
            if f and not (root / f).is_file():
                problems.append(f"manifest.docs[{i}]: file not found: {f}")

    raw_units = m.get("units", [])
    if not isinstance(raw_units, list) or not raw_units:
        problems.append("manifest: 'units' must be a non-empty list")
        raw_units = []

    units: list[Unit] = []
    seen_ids: set[str] = set()
    for i, ru in enumerate(raw_units):
        where = f"manifest.units[{i}]"
        if not isinstance(ru, dict):
            problems.append(f"{where}: must be an object")
            continue
        uid = _req(ru, "id", where, problems, str)
        sig = _req(ru, "signature", where, problems, str)
        if uid is None or sig is None:
            continue
        if not IDENT.match(uid):
            problems.append(f"{where}: id {uid!r} is not a valid python identifier")
        if uid in seen_ids:
            problems.append(f"{where}: duplicate unit id '{uid}'")
        seen_ids.add(uid)

        kind = ru.get("kind", "pure")
        if kind not in UNIT_KINDS:
            problems.append(f"{where}: kind must be one of {sorted(UNIT_KINDS)}, got {kind!r}")
        mutates = ru.get("mutates", [])
        if kind == "stateful" and not mutates:
            problems.append(f"{where}: stateful unit '{uid}' must declare 'mutates'")

        spec_file = ru.get("spec")
        spec_md = ""
        if spec_file:
            p = root / spec_file
            if p.is_file():
                spec_md = p.read_text()
            else:
                problems.append(f"{where}: spec file not found: {spec_file}")

        tests_file = _req(ru, "tests", where, problems, str)
        cases: list[Case] = []
        if tests_file:
            payload = _read_json(root, tests_file, where, problems)
            if payload is not None:
                cases = _parse_cases(payload, f"tests/{uid}", uid, problems)

        units.append(
            Unit(
                id=uid,
                signature=sig,
                kind=kind,
                group=ru.get("group", ""),
                order=ru.get("order", i),
                summary=ru.get("summary", ""),
                spec_file=spec_file,
                tests_file=tests_file,
                mutates=mutates,
                depends_on=ru.get("depends_on", []),
                cases=cases,
                spec_md=spec_md,
            )
        )

    for u in units:
        for dep in u.depends_on:
            if dep not in seen_ids:
                problems.append(f"manifest.units '{u.id}': depends_on unknown unit '{dep}'")

    pipeline_cases: list[Case] = []
    pipeline = m.get("pipeline")
    if not isinstance(pipeline, dict) or "tests" not in pipeline:
        problems.append("manifest: 'pipeline.tests' is required")
    else:
        payload = _read_json(root, pipeline["tests"], "manifest.pipeline", problems)
        if payload is not None and entrypoint:
            pipeline_cases = _parse_cases(payload, "tests/pipeline", entrypoint, problems)

    if problems:
        raise BundleError(problems)

    units.sort(key=lambda u: (u.order, u.id))
    return Bundle(
        id=bid,
        title=title,
        root=root,
        entrypoint=entrypoint,
        language=language,
        skeleton=skeleton,
        source=m.get("source", ""),
        estimated_minutes=m.get("estimated_minutes", 0),
        docs=docs,
        units=units,
        pipeline_cases=pipeline_cases,
        reference=reference,
    )
