import base64
import io

import numpy as np
from PIL import Image
from scipy.spatial import KDTree

# Continental US bounds (must match HEAT_BOUNDS in map_template.py)
LAT_MIN, LAT_MAX = 24.5, 49.5
LON_MIN, LON_MAX = -124.5, -66.5
RESOLUTION = 0.05   # degrees per pixel → ~500 rows × ~1160 cols
MAX_MILES = 300.0   # points beyond this distance are fully transparent

# Colour gradient: intensity 0→1 maps transparent-yellow → orange → red → dark-red
# Each entry: (intensity_threshold, (R, G, B, A))
GRADIENT = [
    (0.0, (255, 255, 178,   0)),   # fully transparent at zero intensity
    (0.3, (253, 141,  60, 160)),   # orange, semi-transparent
    (0.6, (227,  26,  28, 210)),   # red
    (1.0, (128,   0,  38, 230)),   # dark red
]


def compute_heatmap(gyms: list[dict], dpts: list[dict]) -> str:
    """Compute a bottleneck-distance heatmap and return as a base64-encoded PNG."""
    LAT_MI = 69.0
    mid_lat = (LAT_MIN + LAT_MAX) / 2.0
    LON_MI = 69.0 * np.cos(np.radians(mid_lat))

    def to_xy(records: list[dict]) -> np.ndarray:
        return np.array([[r["lat"] * LAT_MI, r["lon"] * LON_MI] for r in records], dtype=np.float64)

    gym_tree = KDTree(to_xy(gyms))
    dpt_tree = KDTree(to_xy(dpts))

    # Build the pixel grid (top→bottom in lat, left→right in lon)
    lats = np.arange(LAT_MAX, LAT_MIN, -RESOLUTION)
    lons = np.arange(LON_MIN, LON_MAX,  RESOLUTION)
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    H, W = grid_lat.shape

    pts = np.stack([grid_lat.ravel() * LAT_MI, grid_lon.ravel() * LON_MI], axis=1)

    gym_dist, _ = gym_tree.query(pts)
    dpt_dist, _ = dpt_tree.query(pts)
    bottleneck = np.maximum(gym_dist, dpt_dist)

    # intensity=1 means "closest to both", intensity=0 means ≥ MAX_MILES away
    intensity = 1.0 - np.clip(bottleneck / MAX_MILES, 0.0, 1.0)

    # Vectorised colour interpolation across gradient stops
    rgba_flat = np.zeros((H * W, 4), dtype=np.float32)
    for i in range(len(GRADIENT) - 1):
        t0, c0 = GRADIENT[i]
        t1, c1 = GRADIENT[i + 1]
        mask = (intensity >= t0) & (intensity <= t1)
        f = np.where(mask, (intensity - t0) / (t1 - t0), 0.0)
        for k in range(4):
            rgba_flat[:, k] += np.where(mask, c0[k] + f * (c1[k] - c0[k]), 0.0)

    # Force fully transparent for pixels with near-zero intensity
    rgba_flat[intensity < 0.01, 3] = 0.0

    rgba = np.clip(rgba_flat, 0, 255).astype(np.uint8).reshape(H, W, 4)

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()
