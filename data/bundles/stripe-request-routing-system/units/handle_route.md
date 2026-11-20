# `handle_route`

Handle one `ROUTE <lat> <lon>` command. The only command that changes `load`.

Exactly 2 valid coordinates, or `"ERROR"` with no change.

Then:

| Case | Output | Example |
|---|---|---|
| A datacenter is chosen | `name distance candidates` | `node-A 0 node-A,node-B` |
| Candidates exist, all full | `None candidates` | `None node-A,node-B` |
| No healthy datacenters | `None` | `None` |

Pick the first ranked candidate with `load < capacity` and add 1 to its load. The candidate list is every ranked name joined by `,` with no spaces -- **including the full ones**. The printed distance is rounded; the ranking used the exact one.
