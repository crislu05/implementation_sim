import math
import re 

EARTH_RADIUS_KM = 6371
MAX_CAPACITY = 1_000_000_000


# ---------- validation helpers ----------

def is_plain_decimal(text):
    # TODO: True only for: optional '-', digits, optional ('.' followed by digits)
    return re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", text) is not None 



def parse_latitude(text):
    # TODO: plain decimal within [-90, 90] -> float, else None  (None = invalid)
    if not is_plain_decimal(text) or not -90 <= float(text) <= 90:
        return None
    
    return float(text)

def parse_longitude(text):
    # TODO: plain decimal within [-180, 180] -> float, else None

    if not is_plain_decimal(text) or not -180 <= float(text) <= 180:
        return None
    
    return float(text)


def parse_capacity(text):
    # TODO: digits only, value from 1 to MAX_CAPACITY -> int, else None
    if not re.fullmatch(r"[0-9]+",text) or not 1 <= int(text) <= MAX_CAPACITY:
        return None
    return int(text)


def parse_health_flag(text):
    # TODO: "true" / "false" in any letter case -> True / False, else None
    lowered = text.lower()
    if lowered == "true":
        return True
    elif lowered == "false":
        return False
    
    return None




# ---------- geometry ----------

def haversine_distance_km(lat1, lon1, lat2, lon2):
    # TODO: convert degrees to radians, apply the Haversine formula
    # TODO: return the EXACT distance (no rounding here)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))



def round_distance(distance_km):
    # TODO: round to the nearest integer for display only
    return int(distance_km + 0.5)


# ---------- command handlers (each returns one output string) ----------

def handle_register(fields, datacenters):
    # fields = [name, lat, lon, capacity]
    # TODO: wrong field count -> "ERROR"
    # TODO: name already registered -> "ERROR"
    # TODO: parse lat, lon, capacity; any None -> "ERROR"
    # TODO: store {lat, lon, capacity, healthy=True, load=0}; return "OK"
    if len(fields) != 4:
        return "ERROR"
    name, lat, lon, capacity = fields

    if name in datacenters:
        return "ERROR"

    lat = parse_latitude(lat)
    lon = parse_longitude(lon)
    capacity = parse_capacity(capacity)

    if lat is None or lon is None or capacity is None:
        return "ERROR"
    
    datacenters[name] = {
        "lat": lat,
        "lon": lon,
        "capacity": capacity,
        "healthy": True,
        "load": 0,
    }

    return "OK"



def handle_set_healthy(fields, datacenters):
    # fields = [name, flag]
    # TODO: wrong field count, unknown name, or invalid flag -> "ERROR"
    # TODO: update healthy; return "OK"
    if len(fields) != 2:
        return "ERROR"
    
    name, flag = fields 

    if name not in datacenters:
        return "ERROR"
    
    flag = parse_health_flag(flag)

    if flag is None:
        return "ERROR"
    
    datacenters[name]["healthy"] = flag 

    return "OK"
    

def handle_distance(fields):
    # fields = [lat1, lon1, lat2, lon2]
    # TODO: wrong field count or any invalid coordinate -> "ERROR"
    # TODO: return the rounded distance as a string
    if len(fields) != 4:
        return "ERROR"

    lat1, lon1, lat2, lon2 = fields 

    lat1 = parse_latitude(lat1)
    lat2 = parse_latitude(lat2)
    lon1 = parse_longitude(lon1)
    lon2 = parse_longitude(lon2)

    if lat1 is None or lat2 is None or lon1 is None or lon2 is None:
        return "ERROR"
    
    harversine_dist = haversine_distance_km(lat1, lon1, lat2, lon2)

    return str(round_distance(harversine_dist))

def rank_healthy_candidates(lat, lon, datacenters):
    # TODO: keep only healthy datacenters
    # TODO: sort by (exact distance, name)
    # TODO: return the ordered list, keeping each exact distance
    available = []

    for datacenter in datacenters:
        if datacenters[datacenter]["healthy"] == False:
            continue 
        else:
            dist = haversine_distance_km(lat, lon, datacenters[datacenter]["lat"], datacenters[datacenter]["lon"])
            available.append((datacenter, dist))
    
    available.sort(key=lambda a: (a[1],a[0]))

    return available
        
        


def handle_route(fields, datacenters):
    # fields = [lat, lon]
    # TODO: wrong field count or invalid coordinates -> "ERROR"
    # TODO: candidates = rank_healthy_candidates(...)
    # TODO: no candidates -> "None"
    # TODO: candidate_names = ranked names joined with ","
    # TODO: first candidate with load < capacity -> load += 1,
    #       return f"{name} {rounded_distance} {candidate_names}"
    # TODO: every candidate full -> f"None {candidate_names}"
    if len(fields) != 2:
        return "ERROR"

    lat, lon = fields 
    lat = parse_latitude(lat)
    lon = parse_longitude(lon)


    if lat is None or lon is None:
        return "ERROR"
    
    candidates = rank_healthy_candidates(lat, lon, datacenters)

    if not candidates:
        return "None"

    available = None 
    for name, dist in candidates:
        if datacenters[name]["load"] < datacenters[name]["capacity"]:
            datacenters[name]["load"] += 1
            available = name 
            distance = round_distance(dist) 
            break 

    candidate_names = (',').join(name for name, dist in candidates)

    if available is None:
        return f"None {candidate_names}"
    
    return f"{available} {distance} {candidate_names}"



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
        if not fields:
            continue 
        command = fields[0]
        arguments = fields[1:]

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
