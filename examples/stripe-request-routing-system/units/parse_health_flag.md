# `parse_health_flag`

Turn a raw field into a boolean.

`true` -> `True`, `false` -> `False`, in **any letter case**. Anything else -> `None`.

`yes`, `1` and `""` are all invalid. Be careful returning `None` rather than `False` for an invalid flag: the caller distinguishes the two.
