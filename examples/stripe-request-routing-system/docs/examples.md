## 7. Examples

### Example 1

```
input = "REGISTER us-west 38 -122 100\nREGISTER us-east 41 -74 150\nREGISTER us-west 50 -100 50\nREGISTER invalid-node 91 0 100\nREGISTER invalid-cap 0 0 0\nSET_HEALTHY us-east false\nSET_HEALTHY fake-node true"
return = ["OK","OK","ERROR","ERROR","ERROR","OK","ERROR"]
```

### Example 2

```
input = "DISTANCE 38 -122 41 -74\nDISTANCE 0 0 0 0\nDISTANCE 91 0 0 0"
return = ["4080","0","ERROR"]
```

### Example 3

```
input = "REGISTER node-A 0 0 1\nREGISTER node-B 0 0 1\nREGISTER node-C 10 10 100\nSET_HEALTHY node-C false\nROUTE 0 0\nROUTE 0 0\nROUTE 0 0"
return = ["OK","OK","OK","OK","node-A 0 node-A,node-B","node-B 0 node-A,node-B","None node-A,node-B"]
```

### Example 4

```
input = "register a 0 0 1\nREGISTER a abc 0 1\nREGISTER a 0 0 1.5\nREGISTER a 0 0\n\nREGISTER a 1.5 -2 1\nROUTE 91 0\nDISTANCE 0 0 0\nPING\nROUTE 1.5 -2"
return = ["ERROR","ERROR","ERROR","ERROR","OK","ERROR","ERROR","ERROR","a 0 a"]
```

### Example 5

```
input = "REGISTER us-west 38 -122 100\nREGISTER us-east 41 -74 150\nREGISTER eu-west 52 0 200\nSET_HEALTHY us-east false\nREGISTER us-west 50 -100 50\nREGISTER invalid 91 0 100\nREGISTER invalid2 0 0 0"
return = ["OK","OK","OK","OK","ERROR","ERROR","ERROR"]
```

### What each example tests

| Example | What it tests |
|---|---|
| 1 and 5 | duplicate names, latitude 91, capacity 0, unknown name in SET_HEALTHY |
| 2 | Haversine result and rounding (`4080`, `0`) |
| 3 | unhealthy nodes skipped, name tie-break, capacity running out, `None` with candidates |
| 4 | lowercase command, non-numeric and decimal inputs, missing fields, blank line, unknown command |
