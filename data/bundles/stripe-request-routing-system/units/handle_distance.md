# `handle_distance`

Handle one `DISTANCE <lat1> <lon1> <lat2> <lon2>` command.

This is the only handler that neither reads nor changes state, so it takes no registry.

Exactly 4 valid coordinates, or `"ERROR"`. Note which bound applies to which field: fields 1 and 3 are latitudes, fields 2 and 4 are longitudes.

Returns the **rounded** distance **as a string**, e.g. `"4080"`.
