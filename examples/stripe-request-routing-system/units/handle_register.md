# `handle_register`

Handle one `REGISTER <name> <lat> <lon> <capacity>` command.

`fields` is the argument list (the command word is already stripped). `datacenters` is the live registry and **this function mutates it**.

1. Exactly 4 fields, or `"ERROR"`.
2. The name must not already exist, or `"ERROR"`.
3. Parse lat, lon and capacity; any `None` -> `"ERROR"`.
4. Store `{lat, lon, capacity, healthy: True, load: 0}` and return `"OK"`.

A failed REGISTER must leave the registry **exactly** as it was -- in particular it does not reserve the name.
