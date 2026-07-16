"""Depth channel via monocular depth estimation (Depth Anything V2).

A hardware depth sensor (stereo rig, LiDAR) delivers per-pixel distance; for
prerecorded aerial video we recover the same signal from a monocular depth
model. Downstream code only needs *relative* distance — absolute scale is
calibrated from detected body heights in the density module.
"""

from __future__ import annotations

import numpy as np

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"


class DepthEstimator:
    def __init__(self, device: str = "cpu", model_id: str = MODEL_ID):
        from transformers import pipeline as hf_pipeline  # deferred: heavy import

        self.pipe = hf_pipeline("depth-estimation", model=model_id, device=device)

    def relative_distance(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Return an (H, W) float32 map of relative distance.

        Unitless but monotonic in true distance, bounded to [1.0, 10.0]
        (1.0 = nearest point in frame, 10.0 = farthest).
        """
        import cv2
        from PIL import Image

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        out = self.pipe(Image.fromarray(rgb))
        pred = out["predicted_depth"]
        if pred.dim() == 3:
            pred = pred.squeeze(0)
        inv = pred.float().cpu().numpy()  # relative inverse depth: higher = closer
        h, w = frame_bgr.shape[:2]
        inv = cv2.resize(inv, (w, h), interpolation=cv2.INTER_LINEAR)
        lo, hi = float(inv.min()), float(inv.max())
        if hi <= lo:
            return np.ones((h, w), dtype=np.float32)
        norm = (inv - lo) / (hi - lo)
        return (1.0 / (0.1 + 0.9 * norm)).astype(np.float32)


def split_sensor_frame(frame_bgr: np.ndarray, side: str) -> tuple[np.ndarray, np.ndarray]:
    """Split a side-by-side depth-sensor recording into (rgb, relative_distance).

    Kinect-style captures store the depth pane next to the RGB pane in one
    video; `side` names the pane holding depth ("left" or "right"). Depth is
    encoded as brightness (brighter = farther, 0 = invalid); invalid pixels
    are filled with the median valid distance. Output range matches the
    monocular estimator: [1.0, 10.0], relative units.
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    half = w // 2
    left, right = frame_bgr[:, :half], frame_bgr[:, half : half * 2]
    depth_pane, rgb = (left, right) if side == "left" else (right, left)

    gray = cv2.cvtColor(depth_pane, cv2.COLOR_BGR2GRAY).astype(np.float32)
    valid = gray > 0
    if valid.any():
        gray = np.where(valid, gray, float(np.median(gray[valid])))
    lo, hi = float(gray.min()), float(gray.max())
    norm = (gray - lo) / (hi - lo) if hi > lo else np.zeros_like(gray)
    return rgb.copy(), (1.0 + 9.0 * norm).astype(np.float32)
