"""Land cover classification from satellite imagery using HSV + ExG."""

import math
import numpy as np
import cv2

from PyQt6.QtGui import QImage


def qpixmap_to_numpy(qpixmap):
    """Convert QPixmap to numpy BGR array."""
    qimage = qpixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
    # RGBA -> BGR
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)


def meters_to_pixels(lat, zoom, meters):
    """Convert meters to pixels at given latitude and zoom level.

    Uses the Web Mercator formula:
    pixels_per_meter = 2^zoom * 256 / (2 * pi * R * cos(lat))
    """
    R = 6378137  # Earth radius in meters (WGS84)
    pixels_per_meter = (2 ** zoom * 256) / (2 * math.pi * R * math.cos(math.radians(lat)))
    return int(meters * pixels_per_meter)


def extract_circle_region(image, center_px, radius_px):
    """Apply circular mask and return masked image + mask.

    Args:
        image: BGR numpy array
        center_px: (cx, cy) tuple, pixel coordinates of circle center
        radius_px: radius in pixels

    Returns:
        (masked_image, mask) where mask is a boolean array of valid pixels
    """
    h, w = image.shape[:2]
    cx, cy = center_px

    # Create coordinate grids
    y, x = np.ogrid[:h, :w]
    dist_sq = (x - cx) ** 2 + (y - cy) ** 2
    mask = dist_sq <= radius_px ** 2

    return image, mask


def classify_landcover(image_bgr, mask=None):
    """Classify land cover using HSV color space + Excess Green Index.

    Args:
        image_bgr: BGR numpy array
        mask: boolean mask of valid pixels (None = use all)

    Returns:
        dict with keys: dense_veg, sparse_veg, bare, built, water
        Values are percentages (0-100) that sum to 100.
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    # Compute Excess Green Index: ExG = 2*g - r - b (normalized)
    bgr_float = image_bgr.astype(np.float32)
    channel_sum = bgr_float.sum(axis=2)
    channel_sum[channel_sum == 0] = 1  # avoid division by zero
    r_norm = bgr_float[:, :, 2] / channel_sum
    g_norm = bgr_float[:, :, 1] / channel_sum
    b_norm = bgr_float[:, :, 0] / channel_sum
    exg = 2 * g_norm - r_norm - b_norm  # range roughly -1 to 1

    h = hsv[:, :, 0]  # 0-179 in OpenCV
    s = hsv[:, :, 1]  # 0-255
    v = hsv[:, :, 2]  # 0-255

    # Scale S and V to 0-100 for thresholding (plan uses 0-100 scale)
    s_pct = s * 100.0 / 255.0
    v_pct = v * 100.0 / 255.0

    # OpenCV hue is 0-179; plan uses 0-180 scale. Map plan thresholds:
    # Plan H:35-85  -> OpenCV ~35-85 (close enough, OpenCV H = degree/2)
    # Plan H:10-30  -> OpenCV ~10-30
    # Plan H:90-130 -> OpenCV ~90-130

    # Water: H:90-130, S>30, V<60
    water = (h >= 90) & (h <= 130) & (s_pct > 30) & (v_pct < 60)

    # Dense Vegetation: H:35-85, S>40, V>30, high ExG
    dense_veg = (h >= 35) & (h <= 85) & (s_pct > 40) & (v_pct > 30) & (exg > 0.05)

    # Sparse Vegetation: H:35-85, S:20-40 or moderate ExG (not already dense)
    sparse_veg_color = (h >= 35) & (h <= 85) & (s_pct >= 20) & (s_pct <= 40)
    sparse_veg_exg = (exg > 0.0) & (exg <= 0.05) & (h >= 25) & (h <= 90)
    sparse_veg = (sparse_veg_color | sparse_veg_exg) & ~dense_veg & ~water

    # Bare Rock/Soil: H:10-30, S:20-60
    bare = (h >= 10) & (h <= 30) & (s_pct >= 20) & (s_pct <= 60) & ~water & ~dense_veg & ~sparse_veg

    # Built-up/Paved: low saturation (grey tones)
    built = (s_pct < 20) & ~water & ~dense_veg & ~sparse_veg & ~bare

    if mask is not None:
        total = mask.sum()
        if total == 0:
            return {"dense_veg": 0, "sparse_veg": 0, "bare": 0, "built": 0, "water": 0}
        counts = {
            "water": int((water & mask).sum()),
            "dense_veg": int((dense_veg & mask).sum()),
            "sparse_veg": int((sparse_veg & mask).sum()),
            "bare": int((bare & mask).sum()),
            "built": int((built & mask).sum()),
        }
    else:
        total = image_bgr.shape[0] * image_bgr.shape[1]
        if total == 0:
            return {"dense_veg": 0, "sparse_veg": 0, "bare": 0, "built": 0, "water": 0}
        counts = {
            "water": int(water.sum()),
            "dense_veg": int(dense_veg.sum()),
            "sparse_veg": int(sparse_veg.sum()),
            "bare": int(bare.sum()),
            "built": int(built.sum()),
        }

    classified = sum(counts.values())
    unclassified = total - classified

    # Distribute unclassified pixels proportionally, or assign to 'bare' if all zero
    if classified > 0:
        for key in counts:
            counts[key] += int(unclassified * counts[key] / classified)
    else:
        counts["bare"] = total

    # Convert to percentages
    total_final = sum(counts.values())
    if total_final == 0:
        total_final = 1
    result = {key: round(val * 100 / total_final) for key, val in counts.items()}

    # Ensure percentages sum to 100
    diff = 100 - sum(result.values())
    if diff != 0:
        # Add/subtract difference to the largest class
        largest = max(result, key=result.get)
        result[largest] += diff

    return result


def analyze_landcover(qpixmap, lat, lng, zoom, radius_m=500):
    """Full analysis pipeline: QPixmap → classification result.

    Args:
        qpixmap: QPixmap of the map view
        lat, lng: center coordinates
        zoom: current map zoom level
        radius_m: analysis radius in meters

    Returns:
        dict with classification percentages
    """
    image = qpixmap_to_numpy(qpixmap)
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    radius_px = meters_to_pixels(lat, zoom, radius_m)

    # Clamp radius to image dimensions
    max_radius = min(center[0], center[1])
    radius_px = min(radius_px, max_radius)

    image, mask = extract_circle_region(image, center, radius_px)
    return classify_landcover(image, mask)
