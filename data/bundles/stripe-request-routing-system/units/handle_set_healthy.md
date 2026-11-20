# `handle_set_healthy`

Handle one `SET_HEALTHY <name> <flag>` command. Mutates `datacenters`.

Exactly 2 fields, a name that exists, and a valid flag -- otherwise `"ERROR"` and no change.

On success it changes **only** the `healthy` field. `load` is left exactly as it was.
