# `round_distance`

Round a distance to an integer, **for display only**.

Python's built-in `round()` sends halves to the nearest *even* number, so `round(2.5) == 2`. That is not what this problem wants. Use $\lfloor d + 0.5 \rfloor$ so halves go up.
