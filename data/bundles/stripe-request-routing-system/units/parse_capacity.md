# `parse_capacity`

Turn a raw field into a capacity, or reject it.

Digits only -- no sign, no decimal point -- with a value from `1` to `MAX_CAPACITY` (1,000,000,000) inclusive. Returns an `int`, or `None`.

`0` is a rejection, not a capacity. So is `1.5`, and so is `-5`.
