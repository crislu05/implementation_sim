# `parse_latitude`

Turn a raw field into a latitude, or reject it.

Returns a `float` when the text is a plain decimal **and** the value is within $[-90, 90]$. Returns `None` otherwise -- `None` is this codebase's "invalid" signal, which is why the parsers never raise.

Check the format first, then the range. Both bounds are inclusive.
