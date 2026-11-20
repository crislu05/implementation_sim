## 1. Context

You are building a small **request router** for datacenters. Commands arrive one per line. You keep a registry of datacenters and send each request to the nearest healthy datacenter that still has space.

Each datacenter has:

- **name**: unique and case-sensitive
- **latitude** and **longitude**
- **capacity**: the most requests it can take
- **healthy**: starts as `true`
- **load**: the number of requests routed to it so far, starts at `0`

## 2. Function signature

```python
def solveRequestRoutingSystem(input: str) -> list[str]
```

- **Input:** one string of commands separated by `\n`.
- **Output:** one string per command, in order.
- Blank or whitespace-only lines produce **no output**.
