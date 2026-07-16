"""Edge-fall risk: depth-cliff hazards + per-person trajectory prediction.

"Will anyone fall off?" — from an aerial view, a drop edge is a sharp
discontinuity in the depth map (beam ends, tier rails, roof openings: the
ground beyond is suddenly much farther away). Each tracked person gets a
velocity vector; walking toward a cliff yields a predicted time-to-edge, and
standing within the safety margin of one flags NEAR EDGE.

Levels: 0 = safe, 1 = NEAR EDGE (within margin of a drop), 2 = FALL RISK
(current path crosses a drop within the prediction horizon).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .detection import Person
from .fall import zone_label

CLIFF_GRAD = 0.4  # relative-distance change per pixel that marks a drop edge
# (tuned on aerial footage: ~1% of pixels, tracing true structure drop-edges)
EDGE_SAFE = 0
EDGE_NEAR = 1
EDGE_FALL_RISK = 2
EDGE_LEVEL_NAMES = {EDGE_SAFE: "SAFE", EDGE_NEAR: "NEAR EDGE", EDGE_FALL_RISK: "FALL RISK"}


def hazard_mask(distance: np.ndarray, grad_thresh: float = CLIFF_GRAD) -> np.ndarray:
    """Boolean map of drop edges: strong local gradients in relative distance."""
    gy, gx = np.gradient(distance.astype(np.float32))
    return np.hypot(gx, gy) > grad_thresh


@dataclass
class EdgeStatus:
    """One person's edge-risk state in the current frame."""

    track_id: int
    level: int
    zone: str
    location: tuple[float, float]
    velocity: tuple[float, float]  # px/s
    tte_s: float | None = None  # predicted time until the path crosses the edge


@dataclass
class EdgeEvent:
    """A confirmed fall-risk episode (for the report timeline)."""

    track_id: int
    start_t: float
    zone: str
    min_tte_s: float | None = None


def global_flow(prev_gray: np.ndarray, gray: np.ndarray) -> tuple[float, float]:
    """Median camera motion (px) between two frames via sparse optical flow.

    A drone never holds still: without ego-motion compensation the whole
    scene "moves", and every stationary person appears to drift toward an
    edge. The median displacement of background corner features is the
    camera's motion; person velocities are measured relative to it.
    """
    import cv2

    corners = cv2.goodFeaturesToTrack(prev_gray, maxCorners=120, qualityLevel=0.01, minDistance=24)
    if corners is None or len(corners) < 8:
        return (0.0, 0.0)
    nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, corners, None)
    good = status.ravel() == 1
    if good.sum() < 8:
        return (0.0, 0.0)
    d = (nxt[good] - corners[good]).reshape(-1, 2)
    return (float(np.median(d[:, 0])), float(np.median(d[:, 1])))


@dataclass
class EdgeMonitor:
    """Tracks motion history and flags people near or heading over drop edges.

    Positions are stored in camera-stabilized coordinates (cumulative global
    flow subtracted) so velocity reflects the person's motion, not the
    drone's.
    """

    fps: float
    near_margin_px: int = 14  # standing this close to a cliff pixel = NEAR EDGE
    horizon_s: float = 1.5  # look this far ahead along the motion vector
    grad_thresh: float = CLIFF_GRAD
    confirm_frames: int = 5  # consecutive FALL RISK frames before an event logs
    cell_px: int = 48
    history_len: int = 6
    events: list[EdgeEvent] = field(default_factory=list)
    _history: dict[int, deque] = field(default_factory=dict)
    _hot: dict[int, int] = field(default_factory=dict)
    _open: dict[int, EdgeEvent] = field(default_factory=dict)
    _cam_x: float = 0.0
    _cam_y: float = 0.0
    _prev_gray: np.ndarray | None = None

    def _velocity(self, tid: int) -> tuple[float, float]:
        h = self._history[tid]
        if len(h) < 2:
            return (0.0, 0.0)
        (x0, y0, f0), (x1, y1, f1) = h[0], h[-1]
        df = max(f1 - f0, 1)
        return ((x1 - x0) * self.fps / df, (y1 - y0) * self.fps / df)

    def update(
        self,
        persons: list[Person],
        distance: np.ndarray | None,
        frame_idx: int,
        t: float,
        frame_shape: tuple[int, ...],
        frame_gray: np.ndarray | None = None,
    ) -> tuple[list[EdgeStatus], np.ndarray | None]:
        """Feed one frame; returns (non-safe statuses, hazard mask or None)."""
        if frame_gray is not None:
            if self._prev_gray is not None:
                dx, dy = global_flow(self._prev_gray, frame_gray)
                self._cam_x += dx
                self._cam_y += dy
            self._prev_gray = frame_gray
        if distance is None:
            return [], None
        mask = hazard_mask(distance, self.grad_thresh)
        h, w = mask.shape
        statuses: list[EdgeStatus] = []
        seen: set[int] = set()

        for p in persons:
            if p.track_id is None:
                continue
            seen.add(p.track_id)
            x, y = p.foot
            hist = self._history.setdefault(p.track_id, deque(maxlen=self.history_len))
            # store camera-stabilized coordinates so velocity is person motion
            hist.append((x - self._cam_x, y - self._cam_y, frame_idx))
            vx, vy = self._velocity(p.track_id)

            level = EDGE_SAFE
            tte: float | None = None

            # NEAR EDGE: any cliff pixel within the safety margin of the feet.
            m = self.near_margin_px
            y0, y1 = max(int(y) - m, 0), min(int(y) + m + 1, h)
            x0, x1 = max(int(x) - m, 0), min(int(x) + m + 1, w)
            if mask[y0:y1, x0:x1].any():
                level = EDGE_NEAR

            # FALL RISK: current velocity carries the person across a cliff
            # pixel within the prediction horizon. Sample the path every ~2 px
            # so a thin edge line can't slip between consecutive samples.
            speed = float(np.hypot(vx, vy))
            if speed > 1e-6:
                path_px = speed * self.horizon_s
                steps = int(np.clip(path_px / 2.0, 8, 64))
                for k in range(1, steps + 1):
                    s = self.horizon_s * k / steps
                    px, py = x + vx * s, y + vy * s
                    if not (0 <= int(px) < w and 0 <= int(py) < h):
                        break
                    if mask[int(py), int(px)]:
                        level = EDGE_FALL_RISK
                        tte = s
                        break

            if level == EDGE_FALL_RISK:
                self._hot[p.track_id] = self._hot.get(p.track_id, 0) + 1
                if self._hot[p.track_id] == self.confirm_frames:
                    ev = EdgeEvent(
                        track_id=p.track_id,
                        start_t=t,
                        zone=zone_label(x, y, self.cell_px, frame_shape),
                        min_tte_s=tte,
                    )
                    self._open[p.track_id] = ev
                    self.events.append(ev)
                if self._hot[p.track_id] < self.confirm_frames:
                    # Not sustained yet: show as NEAR EDGE, don't page anyone.
                    level = EDGE_NEAR
                    tte = None
                ev = self._open.get(p.track_id)
                if ev is not None and tte is not None:
                    ev.min_tte_s = tte if ev.min_tte_s is None else min(ev.min_tte_s, tte)
            else:
                self._hot[p.track_id] = 0
                self._open.pop(p.track_id, None)

            if level != EDGE_SAFE:
                statuses.append(
                    EdgeStatus(
                        track_id=p.track_id,
                        level=level,
                        zone=zone_label(x, y, self.cell_px, frame_shape),
                        location=(x, y),
                        velocity=(vx, vy),
                        tte_s=tte,
                    )
                )

        # Drop history for tracks that vanished a while ago.
        stale = [
            tid
            for tid, hist in self._history.items()
            if hist and frame_idx - hist[-1][2] > 3 * self.fps
        ]
        for tid in stale:
            del self._history[tid]
            self._hot.pop(tid, None)
            self._open.pop(tid, None)

        return statuses, mask
