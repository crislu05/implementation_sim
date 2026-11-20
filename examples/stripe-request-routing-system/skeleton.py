import math

EARTH_RADIUS_KM = 6371
MAX_CAPACITY = 1_000_000_000


# ---------- validation helpers ----------

def is_plain_decimal(text):
    # TODO: True only for: optional '-', digits, optional ('.' followed by digits)
    pass


def parse_latitude(text):
    # TODO: plain decimal within [-90, 90] -> float, else None  (None = invalid)
    pass


def parse_longitude(text):
    # TODO: plain decimal within [-180, 180] -> float, else None
    pass


def parse_capacity(text):
    # TODO: digits only, value from 1 to MAX_CAPACITY -> int, else None
    pass


def parse_health_flag(text):
    # TODO: "true" / "false" in any letter case -> True / False, else None
    pass


# ---------- geometry ----------

def haversine_distance_km(lat1, lon1, lat2, lon2):
    # TODO: convert degrees to radians, apply the Haversine formula
    # TODO: return the EXACT distance (no rounding here)
    pass


def round_distance(distance_km):
    # TODO: round to the nearest integer for display only
    pass


# ---------- command handlers (each returns one output string) ----------

def handle_register(fields, datacenters):
    # fields = [name, lat, lon, capacity]
    # TODO: wrong field count -> "ERROR"
    # TODO: name already registered -> "ERROR"
    # TODO: parse lat, lon, capacity; any None -> "ERROR"
    # TODO: store {lat, lon, capacity, healthy=True, load=0}; return "OK"
    pass


def handle_set_healthy(fields, datacenters):
    # fields = [name, flag]
    # TODO: wrong field count, unknown name, or invalid flag -> "ERROR"
    # TODO: update healthy; return "OK"
    pass


def handle_distance(fields):
    # fields = [lat1, lon1, lat2, lon2]
    # TODO: wrong field count or any invalid coordinate -> "ERROR"
    # TODO: return the rounded distance as a string
    pass


def rank_healthy_candidates(lat, lon, datacenters):
    # TODO: keep only healthy datacenters
    # TODO: sort by (exact distance, name)
    # TODO: return the ordered list, keeping each exact distance
    pass


def handle_route(fields, datacenters):
    # fields = [lat, lon]
    # TODO: wrong field count or invalid coordinates -> "ERROR"
    # TODO: candidates = rank_healthy_candidates(...)
    # TODO: no candidates -> "None"
    # TODO: candidate_names = ranked names joined with ","
    # TODO: first candidate with load < capacity -> load += 1,
    #       return f"{name} {rounded_distance} {candidate_names}"
    # TODO: every candidate full -> f"None {candidate_names}"
    pass


# ---------- main ----------

def solveRequestRoutingSystem(input):
    datacenters = {}  # name -> datacenter record
    outputs = []

    for line in input.split("\n"):
        fields = line.split()
        # TODO: blank line -> skip, no output
        # TODO: command = fields[0], arguments = fields[1:]
        # TODO: send to the matching handler; unknown command -> "ERROR"
        # TODO: append the result to outputs
        pass

    return outputs
