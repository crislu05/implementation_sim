## 4. Validation (any failure returns `ERROR` and changes nothing)

- **Command name:** must match exactly in uppercase. `register` and `PING` are errors.
- **Field count:** must be exact. `DISTANCE 0 0 0` is an error.
- **Coordinate format:** optional leading `-`, then digits, then optionally `.` followed by digits. So `1.5` and `-2` are valid, but `abc`, `+3`, `1e5`, `.5` and `5.` are not.
- **Range:** latitude in $[-90, 90]$ and longitude in $[-180, 180]$. This is checked in **every** command, so `ROUTE 91 0` is an error.
- **Capacity:** digits only, with a value from 1 to 1,000,000,000. `0` and `1.5` are errors.
- **Spacing:** extra spaces between or around fields are fine, so split on any whitespace.

**Constraints:** the input is at most 20,000 characters, printable ASCII plus newlines only, and each field is at most 15 characters.
