# implementation_sim

A local service for practising **implementation** the way it actually happens at work:
a written spec, a decomposed set of functions with real contracts, tests at both the
function and the system level, and a real editor — instead of a single LeetCode prompt.

Everything runs on your machine. Bundles, your code, and every test run are plain files
on local disk.

## Run it

```bash
./run.sh
```

Then open http://127.0.0.1:8420.

The first start creates `.venv` and installs FastAPI. `SIM_HOME` (default `./data`)
controls where bundles and workspaces are stored.

## Load the example problem

```bash
./.venv/bin/python -m simserver.validate examples/stripe-request-routing-system --import
```

Or use **Import** on the library screen — either a `.zip` or a directory path.

## How a session goes

1. Read the problem in the left pane: context, commands, validation rules, worked examples.
2. Switch to **Functions** for the build order. Each function shows its signature, its
   contract, what it depends on, and a status dot.
3. Write code in the middle pane. It autosaves to `data/workspaces/<bundle>/<attempt>/solution.py`.
4. **⌘↵** runs the tests for whichever function your cursor is inside.
   **⌘⇧↵** runs the whole pipeline. **Run all** does everything.
5. Failures show the expected value, what you actually returned, the reason the case
   exists, any state the function should or should not have changed, your `print()`
   output, and a clickable line number for exceptions.

The function tests tell you the pieces are sound. The pipeline tests are the only ones
that say the system works — the gap between them is the point of the exercise.

## What's on disk

```
data/
├── bundles/<bundle-id>/                    imported, validated, read-only
└── workspaces/<bundle-id>/<attempt>/
    ├── solution.py                         your code, autosaved
    └── .sim/
        ├── state.json                      per-function status, elapsed time
        └── runs/<timestamp>.json           every run, in full, append-only
```

Run history is append-only, so an attempt is a replay of how the solution was built.

## Authoring bundles

See [BUNDLE_FORMAT.md](BUNDLE_FORMAT.md). The short version: a bundle ships a reference
solution, and the service runs every test in the bundle against that reference at import
time. A bundle whose own tests disagree with its own reference is **rejected** with a
precise report, so a generated bundle can never reach you in a half-contradictory state.

```bash
./.venv/bin/python -m simserver.validate path/to/bundle          # check
./.venv/bin/python -m simserver.validate path/to/bundle --import # check and install
```

## Layout

| Path | What it is |
|---|---|
| `simserver/schema.py` | bundle format and its validator |
| `simserver/library.py` | import, self-consistency verification |
| `simserver/runner.py` | the subprocess that executes test cases |
| `simserver/execute.py` | spawns and bounds the runner |
| `simserver/workspace.py` | attempts, autosave, run history |
| `simserver/main.py` | HTTP API |
| `simserver/static/` | the three-pane UI (Monaco, no build step) |
| `examples/` | the Stripe request-routing bundle |

## Safety and limits

Runs happen in a fresh subprocess per invocation, with a 2s per-case timeout and a
bounded wall clock for the whole run. This is isolation against your own infinite loops,
not a sandbox — only run bundles you trust.
