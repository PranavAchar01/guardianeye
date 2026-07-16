"""Crush-risk classification from density and crowd motion.

Thresholds follow crowd-safety literature (Fruin's Levels of Service;
G. Keith Still's crowd-density guidance): at sustained ~5+ people/m^2
individuals lose control of their own movement and crowd crush becomes
possible; 6-7 people/m^2 is where fatal compressive asphyxia occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .density import DensityGrid
from .detection import Person

LEVELS = ("SAFE", "MODERATE", "HIGH", "CRITICAL")
DEFAULT_THRESHOLDS = (2.0, 3.5, 5.0)  # people/m^2 boundaries between levels

# BGR colors per level, used by the renderer and the HTML report.
LEVEL_COLORS_BGR = {
    0: (110, 200, 90),
    1: (0, 215, 255),
    2: (0, 140, 255),
    3: (60, 60, 235),
}

STAGNATION_SPEED_MS = 0.3  # below this mean speed a dense crowd is compressing
STAGNATION_DENSITY = 4.0  # people/m^2 needed before stagnation escalates risk


def classify(density: np.ndarray, thresholds: tuple[float, float, float]) -> np.ndarray:
    """Map a density grid to integer risk levels 0..3."""
    t1, t2, t3 = thresholds
    levels = np.zeros(density.shape, dtype=np.int64)
    levels[density >= t1] = 1
    levels[density >= t2] = 2
    levels[density >= t3] = 3
    return levels


def escalate_stagnation(
    levels: np.ndarray,
    density: np.ndarray,
    cell_speeds: dict[tuple[int, int], list[float]],
    density_floor: float = STAGNATION_DENSITY,
    speed_floor: float = STAGNATION_SPEED_MS,
) -> np.ndarray:
    """Escalate HIGH cells to CRITICAL when a dense crowd has stopped moving.

    Stationary, tightly packed crowds ("stop-and-go waves") precede crush
    events even before raw density crosses the critical line.
    """
    out = levels.copy()
    for (r, c), speeds in cell_speeds.items():
        if not speeds:
            continue
        if (
            out[r, c] == 2
            and density[r, c] >= density_floor
            and float(np.mean(speeds)) < speed_floor
        ):
            out[r, c] = 3
    return out


@dataclass
class Zone:
    """A connected region of elevated risk."""

    zone_id: int
    level: int
    peak_density: float
    cells: list[tuple[int, int]]
    centroid_px: tuple[float, float]


def find_zones(
    levels: np.ndarray,
    density: np.ndarray,
    cell_px: int,
    min_level: int = 2,
) -> list[Zone]:
    """4-connected components of cells at or above `min_level`."""
    mask = levels >= min_level
    seen = np.zeros_like(mask, dtype=bool)
    zones: list[Zone] = []
    rows, cols = mask.shape
    for r0 in range(rows):
        for c0 in range(cols):
            if not mask[r0, c0] or seen[r0, c0]:
                continue
            stack = [(r0, c0)]
            seen[r0, c0] = True
            cells: list[tuple[int, int]] = []
            while stack:
                r, c = stack.pop()
                cells.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not seen[nr, nc]:
                        seen[nr, nc] = True
                        stack.append((nr, nc))
            peak = float(max(density[r, c] for r, c in cells))
            level = int(max(levels[r, c] for r, c in cells))
            cy = (sum(r for r, _ in cells) / len(cells) + 0.5) * cell_px
            cx = (sum(c for _, c in cells) / len(cells) + 0.5) * cell_px
            zones.append(
                Zone(
                    zone_id=len(zones) + 1,
                    level=level,
                    peak_density=peak,
                    cells=cells,
                    centroid_px=(cx, cy),
                )
            )
    zones.sort(key=lambda z: z.peak_density, reverse=True)
    for i, z in enumerate(zones):
        z.zone_id = i + 1
    return zones


@dataclass
class AlertEpisode:
    start_t: float
    end_t: float
    peak_density: float


@dataclass
class AlertTracker:
    """Hysteresis so alerts fire on sustained risk, not single-frame flicker."""

    fire_after: int = 8  # consecutive CRITICAL frames before the alert fires
    clear_after: int = 12  # consecutive sub-CRITICAL frames before it clears
    active: bool = False
    episodes: list[AlertEpisode] = field(default_factory=list)
    _hot: int = 0
    _cold: int = 0
    _start_t: float = 0.0
    _peak: float = 0.0
    _streak_start_t: float = 0.0
    _streak_peak: float = 0.0

    def update(self, frame_level: int, peak_density: float, t: float) -> bool:
        """Feed one frame; returns whether the alert is currently active."""
        if frame_level >= 3:
            if self._hot == 0:
                self._streak_start_t = t
                self._streak_peak = peak_density
            self._hot += 1
            self._cold = 0
            self._streak_peak = max(self._streak_peak, peak_density)
        else:
            self._cold += 1
            self._hot = 0

        if not self.active and self._hot >= self.fire_after:
            # The episode began when the hot streak began, not when it fired.
            self.active = True
            self._start_t = self._streak_start_t
            self._peak = self._streak_peak
        elif self.active:
            self._peak = max(self._peak, peak_density)
            if self._cold >= self.clear_after:
                self.active = False
                self.episodes.append(
                    AlertEpisode(start_t=self._start_t, end_t=t, peak_density=self._peak)
                )
        return self.active

    def finalize(self, t: float) -> None:
        """Close an alert that is still active when the video ends."""
        if self.active:
            self.episodes.append(
                AlertEpisode(start_t=self._start_t, end_t=t, peak_density=self._peak)
            )
            self.active = False


def speed_samples_ms(
    tracks_prev: dict[int, tuple[float, float, int]],
    persons_now: list[Person],
    frame_idx: int,
    fps: float,
    grid: DensityGrid,
    max_gap_frames: int = 24,
) -> dict[tuple[int, int], list[float]]:
    """Per-cell person speeds in m/s from track displacement between frames.

    `tracks_prev` maps track_id -> (x, y, frame index of last sighting) and is
    updated in place. Samples in cells with unknown scale (mpp == 0) are
    skipped.
    """
    cell_speeds: dict[tuple[int, int], list[float]] = {}
    for p in persons_now:
        if p.track_id is None:
            continue
        x, y = p.foot
        prev = tracks_prev.get(p.track_id)
        tracks_prev[p.track_id] = (x, y, frame_idx)
        if prev is None:
            continue
        px, py, pf = prev
        dt_frames = frame_idx - pf
        if dt_frames <= 0 or dt_frames > max_gap_frames:
            continue
        mpp = grid.mpp_at(x, y)
        if mpp <= 0:
            continue
        dist_px = float(np.hypot(x - px, y - py))
        speed = dist_px * mpp * fps / dt_frames
        cell_speeds.setdefault(grid.cell_of(x, y), []).append(speed)
    # Drop tracks not seen for a while so stale entries don't accumulate.
    stale = [tid for tid, (_, _, f) in tracks_prev.items() if frame_idx - f > max_gap_frames]
    for tid in stale:
        del tracks_prev[tid]
    return cell_speeds
