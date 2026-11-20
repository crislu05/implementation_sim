"""The bundle library: import, validate, and serve bundles from local disk."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from . import execute
from .schema import Bundle, BundleError, parse_bundle


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, bundle_id: str) -> Path:
        return self.root / bundle_id

    def list(self) -> list[dict]:
        out = []
        for d in sorted(self.root.iterdir()):
            if not (d / "manifest.json").is_file():
                continue
            try:
                b = parse_bundle(d)
                out.append({
                    "id": b.id, "title": b.title, "source": b.source,
                    "units": len(b.units), "pipeline_cases": len(b.pipeline_cases),
                    "estimated_minutes": b.estimated_minutes, "ok": True,
                })
            except BundleError as exc:
                out.append({"id": d.name, "title": d.name, "ok": False,
                            "problems": exc.problems})
        return out

    def load(self, bundle_id: str) -> Bundle:
        return parse_bundle(self.path_for(bundle_id))

    # ---------- import ----------

    def verify(self, root: Path) -> tuple[Bundle, dict]:
        """Structural validation, then run every test against the reference.

        A bundle whose own reference implementation fails its own tests is
        self-inconsistent and is rejected -- this is the guarantee that a
        generated bundle is trustworthy before anyone starts coding against it.
        """
        bundle = parse_bundle(root)
        targets = execute.build_targets(bundle, "all")
        report = execute.run(bundle.root / bundle.reference, targets)

        problems: list[str] = []
        if report.get("fatal"):
            problems.append(f"reference solution: {report['fatal']}")
        if report.get("import_error"):
            err = report["import_error"]
            problems.append(f"reference solution failed to import: {err['type']}: {err['message']}")
        for t in report.get("targets", []):
            if t.get("status") == "not_implemented":
                problems.append(f"reference solution: {t.get('message')}")
            for r in t.get("results", []):
                if r["status"] != "pass":
                    detail = "; ".join(
                        f"{c['label']}: expected {c.get('expected_repr', c.get('expected'))!s}, "
                        f"got {c.get('actual_repr', c.get('actual'))!s}"
                        for c in r.get("checks", []) if not c["ok"]
                    ) or r.get("error", {}).get("message", r["status"])
                    problems.append(
                        f"reference solution fails {t['target']} / case '{r['case_id']}' -- {detail}"
                    )
        if problems:
            raise BundleError(
                ["This bundle is not self-consistent, so it was rejected:"] + problems
            )
        return bundle, execute.summarize(report)

    def import_dir(self, src: Path, overwrite: bool = True) -> tuple[Bundle, dict]:
        bundle, summary = self.verify(src)
        dest = self.path_for(bundle.id)
        if dest.exists():
            if not overwrite:
                raise BundleError([f"bundle '{bundle.id}' already exists"])
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return parse_bundle(dest), summary

    def import_zip(self, data: bytes) -> tuple[Bundle, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "bundle.zip"
            archive.write_bytes(data)
            extract = tmp_path / "extracted"
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    target = (extract / member).resolve()
                    if not str(target).startswith(str(extract.resolve())):
                        raise BundleError([f"unsafe path in archive: {member}"])
                zf.extractall(extract)
            root = extract
            entries = [p for p in extract.iterdir() if not p.name.startswith("__MACOSX")]
            if not (extract / "manifest.json").is_file() and len(entries) == 1 and entries[0].is_dir():
                root = entries[0]
            return self.import_dir(root)
