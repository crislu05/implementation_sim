# `rank_healthy_candidates`

Rank the datacenters that could serve a request from `(lat, lon)`.

Returns a list of `(name, exact_distance_km)` pairs:

1. Keep only records where `healthy` is true.
2. Sort by exact distance, nearest first.
3. Break exact ties by name in character-code order, so `"B" < "a"`.

Keep the exact distance in the pair -- the caller needs it for display, and rounding here would corrupt the ordering.

**Load is irrelevant here.** A full datacenter is still a candidate; it just will not be chosen.
