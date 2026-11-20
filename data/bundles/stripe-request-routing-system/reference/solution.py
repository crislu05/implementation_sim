"""Reference implementation. Never served to the editor; used to verify the bundle."""

import math
import re

EARTH_RADIUS_KM = 6371
MAX_CAPACITY = 1_000_000_000

PLAIN_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")


# ---------- validation helpers ----------

def is_plain_decimal(text):
    return bool(PLAIN_DECIMAL.match(text))


def _parse_coordinate(text, limit):
    if not is_plain_decimal(text):
        return None
    value = float(text)
    if value < -limit or value > limit:
        return None
    return value


def parse_latitude(text):
    return _parse_coordinate(text, 90)


def parse_longitude(text):
    return _parse_coordinate(text, 180)


def parse_capacity(text):
    if not text.isdigit():
        return None
    value = int(text)
    if value < 1 or value > MAX_CAPACITY:
        return None
    return value


def parse_health_flag(text):
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


# ---------- geometry ----------

def haversine_distance_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def round_distance(distance_km):
    return math.floor(distance_km + 0.5)


# ---------- command handlers ----------

def handle_register(fields, datacenters):
    if len(fields) != 4:
        return "ERROR"
    name, raw_lat, raw_lon, raw_capacity = fields
    if name in datacenters:
        return "ERROR"
    lat = parse_latitude(raw_lat)
    lon = parse_longitude(raw_lon)
    capacity = parse_capacity(raw_capacity)
    if lat is None or lon is None or capacity is None:
        return "ERROR"
    datacenters[name] = {"lat": lat, "lon": lon, "capacity": capacity,
                         "healthy": True, "load": 0}
    return "OK"


def handle_set_healthy(fields, datacenters):
    if len(fields) != 2:
        return "ERROR"
    name, raw_flag = fields
    if name not in datacenters:
        return "ERROR"
    flag = parse_health_flag(raw_flag)
    if flag is None:
        return "ERROR"
    datacenters[name]["healthy"] = flag
    return "OK"


def handle_distance(fields):
    if len(fields) != 4:
        return "ERROR"
    lat1 = parse_latitude(fields[0])
    lon1 = parse_longitude(fields[1])
    lat2 = parse_latitude(fields[2])
    lon2 = parse_longitude(fields[3])
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return "ERROR"
    return str(round_distance(haversine_distance_km(lat1, lon1, lat2, lon2)))


def rank_healthy_candidates(lat, lon, datacenters):
    candidates = [
        (name, haversine_distance_km(lat, lon, record["lat"], record["lon"]))
        for name, record in datacenters.items()
        if record["healthy"]
    ]
    candidates.sort(key=lambda pair: (pair[1], pair[0]))
    return candidates


def handle_route(fields, datacenters):
    if len(fields) != 2:
        return "ERROR"
    lat = parse_latitude(fields[0])
    lon = parse_longitude(fields[1])
    if lat is None or lon is None:
        return "ERROR"

    candidates = rank_healthy_candidates(lat, lon, datacenters)
    if not candidates:
        return "None"
    candidate_names = ",".join(name for name, _ in candidates)

    for name, distance in candidates:
        record = datacenters[name]
        if record["load"] < record["capacity"]:
            record["load"] += 1
            return f"{name} {round_distance(distance)} {candidate_names}"
    return f"None {candidate_names}"


# ---------- main ----------

def solveRequestRoutingSystem(input):
    datacenters = {}
    outputs = []

    for line in input.split("\n"):
        fields = line.split()
        if not fields:
            continue
        command, arguments = fields[0], fields[1:]
        if command == "REGISTER":
            outputs.append(handle_register(arguments, datacenters))
        elif command == "SET_HEALTHY":
            outputs.append(handle_set_healthy(arguments, datacenters))
        elif command == "DISTANCE":
            outputs.append(handle_distance(arguments))
        elif command == "ROUTE":
            outputs.append(handle_route(arguments, datacenters))
        else:
            outputs.append("ERROR")

    return outputs
