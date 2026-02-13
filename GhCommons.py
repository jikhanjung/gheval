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
    "LOW": (4, 8),
    "MODERATE": (9, 12),
    "HIGH": (13, 16),
    "CRITICAL": (17, 20),
}

DEFAULT_LATITUDE = 37.5665
DEFAULT_LONGITUDE = 126.9780
DEFAULT_ZOOM = 10


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_data_dir():
    """Get the application data directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    data_dir = os.path.join(base, f".{PROGRAM_NAME.lower()}")
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


def calculate_risk_score(road_proximity, accessibility, vegetation_cover, development_signs):
    """Calculate overall risk score from 4 evaluation criteria (each 1-5)."""
    return road_proximity + accessibility + vegetation_cover + development_signs


def get_risk_level(score):
    """Get risk level string from overall score."""
    for level, (low, high) in RISK_LEVELS.items():
        if low <= score <= high:
            return level
    return "CRITICAL"


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
