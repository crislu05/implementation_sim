## 5. Technical terms

**Great-circle distance:** the shortest distance between two points along the Earth's surface, not in a straight line through it.

**Haversine formula:** the standard way to compute that distance from latitude and longitude. First convert every angle from degrees to **radians**. Then:

$$
a = \sin^2\left(\frac{\Delta\varphi}{2}\right) + \cos\varphi_1 \cos\varphi_2 \sin^2\left(\frac{\Delta\lambda}{2}\right)
$$

$$
d = 2R \arcsin\left(\sqrt{a}\right), \qquad R = 6371 \text{ km}
$$

Here $\varphi$ is latitude, $\lambda$ is longitude, $\Delta\varphi = \varphi_2 - \varphi_1$ and $\Delta\lambda = \lambda_2 - \lambda_1$.

**Test value:** `DISTANCE 38 -122 41 -74` should give `4080`.

**Rounding:** sort on the **exact** distance and round only when you print. Python's `round()` sends halves to the nearest even number (`round(2.5) == 2`). To round halves up, use $\lfloor d + 0.5 \rfloor$.
