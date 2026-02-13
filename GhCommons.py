import os
import sys
import json
import math
import re
import time
import urllib.request
import urllib.error
import urllib.parse

COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "GHEval"
PROGRAM_VERSION = "0.1.0"

APP_TITLE = "GeoHeritage Evaluator"

MAP_TYPES = ["ROADMAP", "SKYVIEW", "SKYVIEW (Summer)", "HYBRID"]

WAYBACK_CONFIG_URL = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"

RISK_LEVELS = {
    "LOW": (2, 4),
    "MODERATE": (5, 6),
    "HIGH": (7, 8),
    "CRITICAL": (9, 10),
}

DEFAULT_LATITUDE = 37.5665
DEFAULT_LONGITUDE = 126.9780
DEFAULT_ZOOM = 10

# Korean Peninsula bounding box (with margin for nearby areas)
KOREA_LAT_RANGE = (33.0, 43.5)
KOREA_LNG_RANGE = (124.0, 132.0)


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_data_dir():
    """Get the application data directory (next to the executable)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller: next to the .exe
        base = os.path.dirname(sys.executable)
    else:
        # Development: next to main.py
        base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_db_path():
    """Get the database file path."""
    return os.path.join(get_data_dir(), f"{PROGRAM_NAME.lower()}.db")


def get_screenshots_dir():
    """Get the screenshots directory path."""
    d = os.path.join(get_data_dir(), "screenshots")
    os.makedirs(d, exist_ok=True)
    return d


def get_photos_dir():
    """Get the photos directory path."""
    d = os.path.join(get_data_dir(), "photos")
    os.makedirs(d, exist_ok=True)
    return d


def calculate_risk_score(road_proximity, vegetation_cover, **_kwargs):
    """Calculate overall risk score from 2 evaluation criteria (each 1-5)."""
    return road_proximity + vegetation_cover


def get_risk_level(score):
    """Get risk level string from overall score."""
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score <= high:
            return level
    return "CRITICAL"


def parse_coordinates(text):
    """Parse various coordinate formats and return (lat, lng) or None.

    Supported formats:
      37.5665, 126.9780              (decimal, comma-separated)
      37.5665 126.9780               (decimal, space-separated)
      37.5665N 126.9780E             (decimal with direction)
      N37.5665 E126.9780             (direction prefix)
      37°33'59.4"N 126°58'40.8"E    (DMS)
      37°33.990'N 126°58.680'E      (degrees decimal minutes)
      37 33 59.4 N, 126 58 40.8 E   (DMS with spaces)
    """
    text = text.strip()
    if not text:
        return None

    # Split into two coordinate parts
    parts = _split_coord_text(text)
    if not parts:
        return None

    coords = []
    for p in parts:
        result = _parse_single_coord(p.strip())
        if result is None:
            return None
        coords.append(result)

    v1, d1 = coords[0]
    v2, d2 = coords[1]

    # If first has E/W or second has N/S, swap
    if d1 in ("E", "W") and d2 not in ("E", "W"):
        return v2, v1
    if d2 in ("N", "S") and d1 not in ("N", "S"):
        return v2, v1
    return v1, v2


def _split_coord_text(text):
    """Split coordinate text into exactly two parts."""
    # Try comma/semicolon first
    for sep in (",", ";"):
        if sep in text:
            parts = [p.strip() for p in text.split(sep, 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                return parts

    # Split after direction letter followed by whitespace
    m = re.match(r"(.+?[NSEWnsew])\s+(.+)", text)
    if m:
        return [m.group(1), m.group(2)]

    # Tab-separated
    if "\t" in text:
        parts = [p.strip() for p in text.split("\t", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts

    # Simple space-separated (two tokens only)
    parts = text.split()
    if len(parts) == 2:
        return parts

    return None


def _parse_single_coord(text):
    """Parse one coordinate component. Returns (value, direction_letter) or None."""
    text = text.strip()

    # Extract direction letter (prefix or suffix)
    direction = ""
    m = re.match(r"^([NSEWnsew])\s*(.*)", text)
    if m:
        direction = m.group(1).upper()
        text = m.group(2).strip()
    else:
        m = re.match(r"(.*?)\s*([NSEWnsew])$", text)
        if m:
            text = m.group(1).strip()
            direction = m.group(2).upper()

    # DMS: 37°33'59.4"
    SEC_MARK = r'[\"\u2033\u201d]'  # ", ″, "
    MIN_MARK = r'[\'\u2032\u2019]'  # ', ′, '
    m = re.match(
        r"(-?)(\d{1,3})\s*°\s*(\d{1,2})\s*" + MIN_MARK + r"\s*"
        r"(\d{1,2}(?:\.\d+)?)\s*" + SEC_MARK + r"?$",
        text,
    )
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * (float(m.group(2)) + float(m.group(3)) / 60 + float(m.group(4)) / 3600)
        if direction in ("S", "W"):
            val = -abs(val)
        return (val, direction)

    # DDM: 37°33.990'
    END_MARK = r'[\'\u2032\"\u2033\u201d\u2019]'
    m = re.match(
        r"(-?)(\d{1,3})\s*°\s*(\d{1,2}(?:\.\d+)?)\s*" + END_MARK + r"?$",
        text,
    )
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * (float(m.group(2)) + float(m.group(3)) / 60)
        if direction in ("S", "W"):
            val = -abs(val)
        return (val, direction)

    # DMS with spaces: 37 33 59.4
    m = re.match(r"(-?)(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}(?:\.\d+)?)$", text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * (float(m.group(2)) + float(m.group(3)) / 60 + float(m.group(4)) / 3600)
        if direction in ("S", "W"):
            val = -abs(val)
        return (val, direction)

    # Decimal: 37.5665 or -37.5665
    m = re.match(r"(-?\d+\.?\d*)\s*°?$", text)
    if m:
        val = float(m.group(1))
        if direction in ("S", "W"):
            val = -abs(val)
        return (val, direction)

    # Fallback: Korean DMS
    result = _parse_korean_dms(text)
    if result:
        return result

    return None


# ── Korean DMS support ──────────────────────────────────

_KOREAN_DIRECTIONS = {
    "북위": "N", "남위": "S", "동경": "E", "서경": "W",
    "북": "N", "남": "S", "동": "E", "서": "W",
}


def _parse_korean_dms(text):
    """Parse a single Korean DMS coordinate component.

    Formats: 37도 33분 59.4초, 37도 33.99분, 37도
    Returns (value, direction_letter) or None.
    """
    # Full DMS: 37도 33분 59.4초
    m = re.match(r"(-?)(\d{1,3})\s*도\s*(\d{1,2})\s*분\s*(\d{1,2}(?:\.\d+)?)\s*초?$", text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * (float(m.group(2)) + float(m.group(3)) / 60 + float(m.group(4)) / 3600)
        return (val, "")

    # DDM: 37도 33.99분
    m = re.match(r"(-?)(\d{1,3})\s*도\s*(\d{1,2}(?:\.\d+)?)\s*분?$", text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * (float(m.group(2)) + float(m.group(3)) / 60)
        return (val, "")

    # Degrees only: 37도
    m = re.match(r"(-?)(\d{1,3}(?:\.\d+)?)\s*도$", text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        val = sign * float(m.group(2))
        return (val, "")

    return None


# ── Coordinate scanning in text ─────────────────────────

# Compiled regex patterns: most-specific → least-specific
_COORD_PATTERNS = []


def _compile_coord_patterns():
    """Compile coordinate scanning regexes (called once on first use)."""
    global _COORD_PATTERNS
    if _COORD_PATTERNS:
        return

    SEC = r'(?:[\"\u2033\u201d]|\'\')'  # ", ″, ", or '' (two single quotes)
    MIN = r'[\'\u2032\u2019]'
    KOR_DIR = r'(?:북위|남위|동경|서경)'

    # 1. Korean DMS pair with direction: 북위 37도 33분 59.4초, 동경 126도 58분 41초
    _COORD_PATTERNS.append(re.compile(
        r'(' + KOR_DIR + r')\s*(\d{1,3})\s*도\s*'
        r'(?:(\d{1,2})\s*분\s*(?:(\d{1,2}(?:\.\d+)?)\s*초?)?)?\s*'
        r'[,\s]*'
        r'(' + KOR_DIR + r')\s*(\d{1,3})\s*도\s*'
        r'(?:(\d{1,2})\s*분\s*(?:(\d{1,2}(?:\.\d+)?)\s*초?)?)?'
    ))

    # 2. Korean DMS pair without direction: 37도 33분 59.4초, 126도 58분 41초
    _COORD_PATTERNS.append(re.compile(
        r'(\d{1,3})\s*도\s*(\d{1,2})\s*분\s*(\d{1,2}(?:\.\d+)?)\s*초?\s*'
        r'[,\s]+\s*'
        r'(\d{1,3})\s*도\s*(\d{1,2})\s*분\s*(\d{1,2}(?:\.\d+)?)\s*초?'
    ))

    # 3. DMS pair with NSEW: 37°33'59"N 126°58'41"E
    _COORD_PATTERNS.append(re.compile(
        r'(\d{1,3})\s*°\s*(\d{1,2})\s*' + MIN + r'\s*'
        r'(\d{1,2}(?:\.\d+)?)\s*' + SEC + r'?\s*([NSns])\s*'
        r'[,\s]*'
        r'(\d{1,3})\s*°\s*(\d{1,2})\s*' + MIN + r'\s*'
        r'(\d{1,2}(?:\.\d+)?)\s*' + SEC + r'?\s*([EWew])'
    ))

    # 4. DDM pair with NSEW: 37°33.990'N 126°58.680'E
    _COORD_PATTERNS.append(re.compile(
        r'(\d{1,3})\s*°\s*(\d{1,2}(?:\.\d+)?)\s*' + MIN + r'\s*([NSns])\s*'
        r'[,\s]*'
        r'(\d{1,3})\s*°\s*(\d{1,2}(?:\.\d+)?)\s*' + MIN + r'\s*([EWew])'
    ))

    # 5. Decimal with direction letters: 37.5665N, 126.978E
    _COORD_PATTERNS.append(re.compile(
        r'(\d{1,3}\.\d+)\s*°?\s*([NSns])\s*'
        r'[,\s]+\s*'
        r'(\d{1,3}\.\d+)\s*°?\s*([EWew])'
    ))

    # 6. Plain decimal pair (strict: 2+ decimal places, range validation)
    _COORD_PATTERNS.append(re.compile(
        r'(?<![.\d])'
        r'(-?\d{1,3}\.\d{2,})\s*[,\s]+\s*(-?\d{1,3}\.\d{2,})'
        r'(?![.\d])'
    ))


def _korean_dms_to_decimal(deg, minutes=None, seconds=None):
    """Convert DMS components to decimal degrees."""
    val = float(deg)
    if minutes is not None:
        val += float(minutes) / 60
    if seconds is not None:
        val += float(seconds) / 3600
    return val


def scan_coordinates_in_text(text):
    """Scan text for coordinate pairs. Returns list of (lat, lng, matched_text)."""
    _compile_coord_patterns()

    # Normalize whitespace
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    results = []

    for i, pattern in enumerate(_COORD_PATTERNS):
        for m in pattern.finditer(text):
            matched = m.group(0)
            coord = None

            if i == 0:  # Korean DMS with direction
                dir1 = _KOREAN_DIRECTIONS.get(m.group(1), "")
                dir2 = _KOREAN_DIRECTIONS.get(m.group(5), "")
                v1 = _korean_dms_to_decimal(m.group(2), m.group(3), m.group(4))
                v2 = _korean_dms_to_decimal(m.group(6), m.group(7), m.group(8))
                if dir1 in ("S", "W"):
                    v1 = -v1
                if dir2 in ("S", "W"):
                    v2 = -v2
                # Assign lat/lng based on direction
                if dir1 in ("N", "S") and dir2 in ("E", "W"):
                    coord = (v1, v2)
                elif dir1 in ("E", "W") and dir2 in ("N", "S"):
                    coord = (v2, v1)
                else:
                    coord = (v1, v2)  # assume lat, lng order

            elif i == 1:  # Korean DMS without direction
                v1 = _korean_dms_to_decimal(m.group(1), m.group(2), m.group(3))
                v2 = _korean_dms_to_decimal(m.group(4), m.group(5), m.group(6))
                coord = (v1, v2)  # assume lat, lng order

            elif i == 2:  # DMS with NSEW
                v1 = float(m.group(1)) + float(m.group(2)) / 60 + float(m.group(3)) / 3600
                v2 = float(m.group(5)) + float(m.group(6)) / 60 + float(m.group(7)) / 3600
                if m.group(4).upper() == "S":
                    v1 = -v1
                if m.group(8).upper() == "W":
                    v2 = -v2
                coord = (v1, v2)

            elif i == 3:  # DDM with NSEW
                v1 = float(m.group(1)) + float(m.group(2)) / 60
                v2 = float(m.group(4)) + float(m.group(5)) / 60
                if m.group(3).upper() == "S":
                    v1 = -v1
                if m.group(6).upper() == "W":
                    v2 = -v2
                coord = (v1, v2)

            elif i == 4:  # Decimal with direction
                v1 = float(m.group(1))
                v2 = float(m.group(3))
                if m.group(2).upper() == "S":
                    v1 = -v1
                if m.group(4).upper() == "W":
                    v2 = -v2
                coord = (v1, v2)

            elif i == 5:  # Plain decimal
                v1 = float(m.group(1))
                v2 = float(m.group(2))
                coord = (v1, v2)

            if coord:
                lat, lng = coord
                if i == 5:  # plain decimal — restrict to Korea range
                    if (KOREA_LAT_RANGE[0] <= lat <= KOREA_LAT_RANGE[1]
                            and KOREA_LNG_RANGE[0] <= lng <= KOREA_LNG_RANGE[1]):
                        results.append((lat, lng, matched))
                elif -90 <= lat <= 90 and -180 <= lng <= 180:
                    results.append((lat, lng, matched))

    return _deduplicate_coords(results)


def _deduplicate_coords(coords, tolerance=0.001):
    """Remove near-duplicate coordinates. Keeps first occurrence."""
    unique = []
    for lat, lng, text in coords:
        is_dup = False
        for ulat, ulng, _ in unique:
            if abs(lat - ulat) < tolerance and abs(lng - ulng) < tolerance:
                is_dup = True
                break
        if not is_dup:
            unique.append((lat, lng, text))
    return unique


def fetch_road_distance(lat, lng, timeout=20):
    """Fetch distance to nearest qualifying road using Overpass API.

    Includes: trunk, primary, secondary, tertiary (국도/지방도/시군도).
    Excludes: motorway (고속도로), residential/service (골목길).

    Returns (distance_m, snap_lat, snap_lng) tuple.
    """
    radius = 5000  # 5km search radius
    highway_filter = (
        "trunk|trunk_link|primary|primary_link"
        "|secondary|secondary_link|tertiary|tertiary_link"
    )
    query = (
        f'[out:json][timeout:{timeout}];'
        f'way(around:{radius},{lat},{lng})'
        f'["highway"~"^({highway_filter})$"];'
        f'(._;>;);out;'
    )

    url = "https://overpass-api.de/api/interpreter"
    post_data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        url, data=post_data, headers={"User-Agent": "GHEval/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    # Build node coordinate lookup
    nodes = {}
    for elem in result.get("elements", []):
        if elem["type"] == "node":
            nodes[elem["id"]] = (elem["lat"], elem["lon"])

    # Find closest point on any way segment
    min_dist = float("inf")
    closest_lat, closest_lng = lat, lng

    for elem in result.get("elements", []):
        if elem["type"] != "way":
            continue
        nids = elem.get("nodes", [])
        way_nodes = [nodes[nid] for nid in nids if nid in nodes]
        for i in range(len(way_nodes) - 1):
            clat, clng, dist = _closest_point_on_segment(
                lat, lng,
                way_nodes[i][0], way_nodes[i][1],
                way_nodes[i + 1][0], way_nodes[i + 1][1],
            )
            if dist < min_dist:
                min_dist = dist
                closest_lat, closest_lng = clat, clng

    if min_dist == float("inf"):
        raise RuntimeError("No qualifying roads (국도/지방도) found within 5 km")

    return min_dist, closest_lat, closest_lng


def _closest_point_on_segment(plat, plng, alat, alng, blat, blng):
    """Find closest point on line segment A->B to point P (all in lat/lng).

    Returns (lat, lng, distance_meters).
    """
    cos_lat = math.cos(math.radians(plat))
    m_per_deg_lat = 111320.0
    m_per_deg_lng = 111320.0 * cos_lat

    # Convert to local meters centered at P
    ax = (alng - plng) * m_per_deg_lng
    ay = (alat - plat) * m_per_deg_lat
    bx = (blng - plng) * m_per_deg_lng
    by = (blat - plat) * m_per_deg_lat

    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        return alat, alng, math.sqrt(ax * ax + ay * ay)

    # Projection parameter t, clamped to [0, 1]
    t = max(0.0, min(1.0, (-ax * dx - ay * dy) / seg_len_sq))

    # Closest point in local meters
    cx = ax + t * dx
    cy = ay + t * dy
    dist = math.sqrt(cx * cx + cy * cy)

    # Convert back to lat/lng
    clat = plat + cy / m_per_deg_lat
    clng = plng + cx / m_per_deg_lng
    return clat, clng, dist


def road_distance_to_score(distance_m):
    """Convert road distance in meters to a 1-5 risk score.

    >1000m -> 1 (Far), 500-1000m -> 2 (Distant), 200-500m -> 3 (Moderate),
    50-200m -> 4 (Near), <50m -> 5 (Adjacent)
    """
    if distance_m > 1000:
        return 1
    elif distance_m > 500:
        return 2
    elif distance_m > 200:
        return 3
    elif distance_m > 50:
        return 4
    else:
        return 5


def _load_wayback_config(force_refresh=False):
    """Load Wayback config with 24h file cache."""
    cache_path = os.path.join(get_data_dir(), "wayback_config.json")

    if not force_refresh and os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        if time.time() - mtime < 86400:
            with open(cache_path, 'r') as f:
                return json.load(f)

    req = urllib.request.Request(WAYBACK_CONFIG_URL, headers={"User-Agent": "GHEval/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8")
    with open(cache_path, 'w') as f:
        f.write(data)
    return json.loads(data)


def fetch_wayback_summer_version(force_refresh=False):
    """Fetch a summer Wayback version by release date (fallback).

    Returns (release_num, date_str, metadata_url) or None.
    """
    config = _load_wayback_config(force_refresh)
    return _find_summer_by_release_date(config)


def fetch_wayback_summer_by_capture(lat, lng, force_refresh=False,
                                    max_tries=30, progress_callback=None):
    """Find Wayback version where imagery at (lat, lng) was captured in summer.

    Search strategy (within recent 5 years):
    1. Return immediately if capture date is June-August.
    2. Otherwise, return the version whose capture date is closest to July 1st.
    Falls back to release-date-based search if nothing found.
    Returns (release_num, date_str, metadata_url) or None.
    """
    config = _load_wayback_config(force_refresh)

    # Collect all versions with metadata URLs, sorted newest first
    versions = []
    for release_num, info in config.items():
        m = re.search(r'Wayback (\d{4}-\d{2}-\d{2})', info.get("itemTitle", ""))
        metadata_url = info.get("metadataLayerUrl", "")
        if m and metadata_url:
            versions.append((m.group(1), int(release_num), metadata_url))
    versions.sort(reverse=True)

    geom = json.dumps({"x": lng, "y": lat, "spatialReference": {"wkid": 4326}})
    seen_dates = set()
    tries = min(len(versions), max_tries)
    cutoff_ts = time.time() - 5 * 365.25 * 86400  # 5 years ago
    JULY1_YDAY = 182  # July 1st ≈ day 182

    # Track best fallback: closest capture date to July 1st
    best = None  # (day_distance, release_num, date_str, metadata_url)

    for i, (date_str, release_num, metadata_url) in enumerate(versions[:tries]):
        if progress_callback:
            progress_callback(f"Checking imagery {i + 1}/{tries}...")

        try:
            query_url = (
                f"{metadata_url}/5/query"
                f"?f=json&returnGeometry=false&spatialRel=esriSpatialRelIntersects"
                f"&geometryType=esriGeometryPoint"
                f"&geometry={urllib.parse.quote(geom)}"
                f"&outFields=SRC_DATE2"
            )
            req = urllib.request.Request(query_url, headers={"User-Agent": "GHEval/0.1"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            features = data.get("features", [])
            if features:
                src_date = features[0].get("attributes", {}).get("SRC_DATE2")
                if src_date:
                    if src_date in seen_dates:
                        continue
                    seen_dates.add(src_date)

                    ts = src_date / 1000
                    if ts < cutoff_ts:
                        continue  # older than 5 years, skip

                    tm = time.gmtime(ts)

                    # Exact summer → return immediately
                    if tm.tm_mon in (6, 7, 8):
                        return (release_num, date_str, metadata_url)

                    # Track closest to July 1st
                    dist = abs(tm.tm_yday - JULY1_YDAY)
                    if best is None or dist < best[0]:
                        best = (dist, release_num, date_str, metadata_url)
        except Exception:
            continue

    # Return closest-to-July-1st if found within 5 years
    if best:
        if progress_callback:
            progress_callback("Using closest to summer...")
        return (best[1], best[2], best[3])

    # Fallback: latest version available
    if versions:
        v = versions[0]
        return (v[1], v[0], v[2])
    return None


def _find_summer_by_release_date(config):
    """Find the latest summer (June-August) version by release date.

    Returns (release_num, date_str, metadata_url) or None.
    """
    summer_versions = []
    for release_num, info in config.items():
        m = re.search(r'Wayback (\d{4}-(\d{2})-\d{2})', info.get("itemTitle", ""))
        if m and int(m.group(2)) in (6, 7, 8):
            metadata_url = info.get("metadataLayerUrl", "")
            summer_versions.append((m.group(1), int(release_num), metadata_url))
    summer_versions.sort(reverse=True)  # newest date first
    if summer_versions:
        return (summer_versions[0][1], summer_versions[0][0], summer_versions[0][2])
    return None
