import os
import sys
import json
import math
import urllib.request
import urllib.error

COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "GHEval"
PROGRAM_VERSION = "0.1.0"

APP_TITLE = "GeoHeritage Evaluator"

MAP_TYPES = ["ROADMAP", "SKYVIEW", "HYBRID"]

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


def fetch_road_distance(lat, lng, timeout=10):
    """Fetch distance (meters) to nearest road using OSRM Nearest API.

    Returns (distance_m, snap_lat, snap_lng) tuple.
    """
    url = (
        f"https://router.project-osrm.org/nearest/v1/driving/"
        f"{lng},{lat}?number=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "GHEval/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("code") != "Ok" or not data.get("waypoints"):
        raise RuntimeError(f"OSRM API error: {data.get('code', 'Unknown')}")

    wp = data["waypoints"][0]
    snap_lat, snap_lng = wp["location"][1], wp["location"][0]
    distance = _haversine(lat, lng, snap_lat, snap_lng)
    return distance, snap_lat, snap_lng


def _haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
