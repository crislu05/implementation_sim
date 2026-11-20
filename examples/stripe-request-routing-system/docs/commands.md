## 3. Commands

Every command arrives as **one line of text**, split on whitespace into string fields. You parse each field into its real type, and every command returns **one string**.

### Overview

| Command | Fields | Returns |
|---|---|---|
| `REGISTER` | `name lat lon capacity` | `OK`, or `ERROR` |
| `SET_HEALTHY` | `name flag` | `OK`, or `ERROR` |
| `DISTANCE` | `lat1 lon1 lat2 lon2` | the rounded distance in km, e.g. `4080`, or `ERROR` |
| `ROUTE` | `lat lon` | chosen datacenter and candidates, `None ...`, `None`, or `ERROR` |

### REGISTER: add a new datacenter

```
REGISTER <name> <lat> <lon> <capacity>
```

| Field | Arrives as | Parse to | Rule |
|---|---|---|---|
| name | `str` | `str` | must not already exist |
| lat | `str` | `float` | plain decimal in $[-90, 90]$ |
| lon | `str` | `float` | plain decimal in $[-180, 180]$ |
| capacity | `str` | `int` | digits only, 1 to $10^9$ |

On success it stores a new record with `healthy = True` and `load = 0`. A failed REGISTER does **not** reserve the name.

| Line | Output | Why |
|---|---|---|
| `REGISTER us-west 38 -122 100` | `OK` | all valid |
| `REGISTER a 1.5 -2 1` | `OK` | decimals are fine for coordinates |
| `REGISTER us-west 50 -100 50` | `ERROR` | name already taken |
| `REGISTER x 91 0 100` | `ERROR` | latitude out of range |
| `REGISTER x 0 0 1.5` | `ERROR` | capacity isn't whole |
| `REGISTER x 0 0` | `ERROR` | missing a field |

### SET_HEALTHY: turn a datacenter on or off

```
SET_HEALTHY <name> <flag>
```

| Field | Arrives as | Parse to | Rule |
|---|---|---|---|
| name | `str` | `str` | must already exist |
| flag | `str` | `bool` | `true` or `false`, any letter case |

It changes only the `healthy` field. Load is left as it is.

| Line | Output | Why |
|---|---|---|
| `SET_HEALTHY us-east false` | `OK` | exists, valid flag |
| `SET_HEALTHY us-east TRUE` | `OK` | letter case doesn't matter |
| `SET_HEALTHY fake-node true` | `ERROR` | no such datacenter |
| `SET_HEALTHY us-east yes` | `ERROR` | invalid flag |

### DISTANCE: a calculator for two points

```
DISTANCE <lat1> <lon1> <lat2> <lon2>
```

All four fields are `float` coordinates with the same rules as REGISTER. This command **doesn't read or change any state**. It returns the Haversine distance rounded to an integer, as a string.

| Line | Output | Why |
|---|---|---|
| `DISTANCE 38 -122 41 -74` | `4080` | San Francisco area to New York area |
| `DISTANCE 0 0 0 0` | `0` | same point |
| `DISTANCE 91 0 0 0` | `ERROR` | latitude out of range |
| `DISTANCE 0 0 0` | `ERROR` | only three fields |

### ROUTE: send one request to a datacenter

```
ROUTE <lat> <lon>
```

The two fields are `float` coordinates (where the request comes from). This is the only command that changes `load`.

Steps:

1. Candidates are all **healthy** datacenters.
2. Sort them by **exact** distance, nearest first. On an exact tie, sort by name in character-code order (`"B" < "a"`).
3. Pick the first candidate with `load < capacity` and add 1 to its load.
4. Format the output:

| Case | Output | Example |
|---|---|---|
| A datacenter is chosen | `name distance candidates` | `node-A 0 node-A,node-B` |
| Candidates exist, all full | `None candidates` | `None node-A,node-B` |
| No healthy datacenters | `None` | `None` |

The parts are separated by single spaces. Candidates are joined with commas (no spaces), in ranked order, and full candidates are included.

Walkthrough using Example 3, where node-A and node-B sit at (0, 0) with capacity 1 and node-C is unhealthy:

| Line | Output | Why |
|---|---|---|
| `ROUTE 0 0` | `node-A 0 node-A,node-B` | tie on distance, so A wins by name; A's load becomes 1 |
| `ROUTE 0 0` | `node-B 0 node-A,node-B` | A is full, so B is chosen |
| `ROUTE 0 0` | `None node-A,node-B` | both full; candidates still listed |
| `ROUTE 0 0` (none healthy) | `None` | no candidates at all |
| `ROUTE 91 0` | `ERROR` | latitude out of range |

### Data model

```python
datacenters = {
    "node-A": {"lat": 0.0, "lon": 0.0, "capacity": 1, "healthy": True, "load": 0},
}
```

| Command | Reads state | Changes state |
|---|---|---|
| REGISTER | checks whether the name exists | adds a record |
| SET_HEALTHY | finds the record | changes `healthy` |
| DISTANCE | no | no |
| ROUTE | all healthy records | changes `load` of one record |
