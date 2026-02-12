import os
import sys

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
