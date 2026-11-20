# `haversine_distance_km`

The great-circle distance in km between two points, using the Haversine formula with $R = 6371$ km.

Convert every angle from degrees to **radians** first.

$$a = \sin^2\left(\frac{\Delta\varphi}{2}\right) + \cos\varphi_1 \cos\varphi_2 \sin^2\left(\frac{\Delta\lambda}{2}\right)$$

$$d = 2R \arcsin\left(\sqrt{a}\right)$$

**Return the exact distance. Do not round here** -- ranking depends on the exact value and only display rounds.

Anchor: `(38, -122)` to `(41, -74)` is about `4080.006` km.
