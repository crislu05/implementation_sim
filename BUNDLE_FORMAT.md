# Bundle format v1.0

A **bundle** is one practice problem: the prose a candidate reads, the skeleton they
start from, the per-function contracts, and every test. It is a directory, shipped as
a `.zip` or imported from a path.

A bundle is only accepted if it is **self-consistent**: the service runs every test in
the bundle against the bundle's own `reference/solution.py` at import time and rejects
the bundle if a single case fails. Generate the reference implementation as carefully
as the tests — it is the thing that proves the spec, the tests, and the skeleton agree.

Check a bundle before shipping it:

```bash
./.venv/bin/python -m simserver.validate path/to/bundle
```

## Layout

```
<bundle-id>/
├── manifest.json            index + contract (the only file parsed to bootstrap)
├── docs/*.md                the problem as the user reads it
├── skeleton.py              the starting code the editor opens
├── units/<fn>.md            one spec per function
├── tests/units/<fn>.json    one test file per function
├── tests/pipeline.json      end-to-end tests for the entrypoint
└── reference/solution.py    complete working solution (never shown to the user)
```

## manifest.json

```json
{
  "bundle_version": "1.0",
  "id": "stripe-request-routing-system",
  "title": "Request Routing System",
  "source": "Stripe",
  "language": "python",
  "estimated_minutes": 75,
  "entrypoint": "solveRequestRoutingSystem",
  "skeleton": "skeleton.py",
  "reference": "reference/solution.py",
  "docs": [
    { "id": "overview", "title": "Context", "file": "docs/overview.md" }
  ],
  "units": [
    {
      "id": "parse_latitude",
      "signature": "def parse_latitude(text: str) -> float | None",
      "kind": "pure",
      "group": "validation helpers",
      "order": 2,
      "summary": "plain decimal within [-90, 90], else None",
      "depends_on": ["is_plain_decimal"],
      "mutates": [],
      "spec": "units/parse_latitude.md",
      "tests": "tests/units/parse_latitude.json"
    }
  ],
  "pipeline": { "tests": "tests/pipeline.json" }
}
```

| Field | Meaning |
|---|---|
| `entrypoint` | the one function the pipeline tests call |
| `units[].id` | must be a top-level `def` of that exact name in the skeleton |
| `units[].kind` | `pure` (return value only) or `stateful` (also mutates an argument) |
| `units[].mutates` | required for `stateful`: which argument names are mutated |
| `units[].depends_on` | other unit ids; drives the build-order view and dependency links |
| `units[].order` | the order a person should build them in, 1-based |
| `units[].group` | section heading in the function list |

The signature is a **contract**. The runner calls `getattr(module, id)` directly, so a
renamed or re-arged function is reported as "not written yet" rather than silently skipped.

## Test files

```json
{
  "target": "handle_register",
  "cases": [
    {
      "id": "duplicate-name",
      "why": "the name is taken, and the existing record must not change",
      "tags": ["error", "state"],
      "visible": true,
      "given": {
        "dcs": { "us-west": { "lat": 38.0, "lon": -122.0, "capacity": 100,
                              "healthy": true, "load": 0 } }
      },
      "args": [["us-west", "50", "-100", "50"], "$given.dcs"],
      "expect": {
        "returns": "ERROR",
        "state": { "dcs": { "us-west": { "lat": 38.0, "lon": -122.0, "capacity": 100,
                                         "healthy": true, "load": 0 } } }
      }
    }
  ]
}
```

- `target` must equal the unit id (or the entrypoint, for `pipeline.json`).
- `args` is the argument list, as JSON. The single escape is the string `"$given.<name>"`,
  which is replaced by the live fixture object so mutation is observable.
- `given` declares fixtures. Each case gets a fresh deep copy, so cases never leak into
  each other.
- `expect.returns` is the expected return value. `expect.state` is checked only for
  `stateful` units and names fixtures from `given`.
- `why` is shown next to the case in the UI. Write it as the reason the case exists,
  not a restatement of the inputs — this is the most useful feedback the user gets.
- `tags` are free-form; `trap` is highlighted in the UI for cases that catch a
  predictable mistake (banker's rounding, a reserved name on failure, etc).
- `visible` is reserved for a future hidden-test mode. Leave it `true` in v1.

### Comparison modes

`expect.match` defaults to `equal`.

| `match` | Use for | Extra fields |
|---|---|---|
| `equal` | exact structural equality; `True` never equals `1`, tuples match lists | — |
| `approx` | floats, recursively through lists and dicts | `tol` (default `1e-6`) |
| `unordered` | a collection whose order is not part of the contract | — |
| `is_none` | the function must return `None`; do **not** also set `returns` | — |
| `raises` | the call must raise | `raises`: the exception class name |

## Writing good units

1. **Decompose far enough that each unit is independently testable.** Validation helpers,
   pure computation, and each command handler are separate units. If a unit can only be
   tested through another unit, the split is wrong.
2. **Every unit returns a value.** A unit that only mutates is hard to test and hard to
   reason about; have it return a status as well.
3. **Pin the invalid signal.** This bundle uses `None` for "invalid". Say so in the spec
   and test it, otherwise the user will raise an exception instead and every caller breaks.
4. **Put traps in their own cases, tagged `trap`,** with a `why` that names the trap.
5. **Cover the state that must NOT change** on an error path. That is where real
   implementations leak, and it is what separates this from LeetCode.
