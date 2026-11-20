# `is_plain_decimal`

Decide whether a raw field looks like a plain decimal number.

**Valid:** an optional leading `-`, then one or more digits, then optionally a `.` followed by one or more digits.

| Input | Result | Why |
|---|---|---|
| `1.5` | `True` | digits, dot, digits |
| `-2` | `True` | a leading minus is allowed |
| `+3` | `False` | a leading plus is not |
| `1e5` | `False` | scientific notation is not plain |
| `.5` | `False` | digits are required before the dot |
| `5.` | `False` | digits are required after the dot |

This is a *format* check only. Range is somebody else's job.
