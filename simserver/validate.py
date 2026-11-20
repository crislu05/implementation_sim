"""CLI: check a bundle without going near the UI.

    python -m simserver.validate path/to/bundle [--import]

Exit code 0 means the bundle is structurally valid AND its own reference
implementation passes every test it ships.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .library import Library
from .schema import BundleError

SIM_HOME = Path(__file__).resolve().parent.parent / "data"


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    do_import = "--import" in argv
    if not args:
        print(__doc__)
        return 2

    src = Path(args[0]).expanduser()
    lib = Library(SIM_HOME / "bundles")
    try:
        if do_import:
            bundle, summary = lib.import_dir(src)
            where = f"imported to {lib.path_for(bundle.id)}"
        else:
            bundle, summary = lib.verify(src)
            where = "not imported (pass --import to install it)"
    except BundleError as exc:
        print(f"\n  BUNDLE REJECTED: {src}\n")
        for p in exc.problems:
            print(f"    {p}")
        print()
        return 1

    print(f"\n  OK  {bundle.title}  [{bundle.id}]")
    print(f"      {len(bundle.units)} functions, {len(bundle.pipeline_cases)} pipeline cases")
    print(f"      reference passes {summary['passed']}/{summary['total']} cases")
    print(f"      {where}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
