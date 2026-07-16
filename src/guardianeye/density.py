"""People-per-square-meter estimation on a coarse ground grid.

Scale recovery: every detected person is a ruler. Assuming a mean standing
height of REF_HEIGHT_M, the meters-per-pixel (mpp) at a person's location is
REF_HEIGHT_M / bbox_height_px. The depth map extends that sparse scale to the
whole frame — under a pinhole camera the pixel footprint grows linearly with
distance — yielding real-world cell areas and therefore absolute density.

Pure NumPy on tiny grids (~12x16); no ML dependencies, fully unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .detection import Person

REF_HEIGHT_M = 1.7  # assumed mean standing height of a detected person
MIN_BOX_PX = 8.0  # boxes shorter than this are too noisy to use as rulers
MAX_RULER_ASPECT = 0.8  # wider boxes are lying/seated people, not vertical rulers


@dataclass
class DensityGrid:
    """Per-frame density estimate over a coarse grid."""

    density: np.ndarray  # (rows, cols) people per m^2
    counts: np.ndarray  # (rows, cols) raw person counts
    mpp: np.ndarray  # (rows, cols) meters per pixel (0 where unknown)
    cell_px: int

    @property
    def max_density(self) -> float:
        return float(self.density.max()) if self.density.size else 0.0

    @property
    def occupied_mean(self) -> float:
        occ = self.density[self.counts > 0]
        return float(occ.mean()) if occ.size else 0.0

    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        return cell_of(x, y, self.cell_px, self.density.shape)

    def mpp_at(self, x: float, y: float) -> float:
        r, c = self.cell_of(x, y)
        return float(self.mpp[r, c])


def grid_shape(frame_shape: tuple[int, ...], cell_px: int) -> tuple[int, int]:
    h, w = frame_shape[0], frame_shape[1]
    return (max(1, math.ceil(h / cell_px)), max(1, math.ceil(w / cell_px)))


def cell_of(x: float, y: float, cell_px: int, shape: tuple[int, int]) -> tuple[int, int]:
    r = min(max(int(y // cell_px), 0), shape[0] - 1)
    c = min(max(int(x // cell_px), 0), shape[1] - 1)
    return r, c


def block_mean(arr: np.ndarray, cell_px: int, gshape: tuple[int, int]) -> np.ndarray:
    """Mean of `arr` over each grid cell (partial edge cells included)."""
    rows, cols = gshape
    out = np.zeros((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            blk = arr[r * cell_px : (r + 1) * cell_px, c * cell_px : (c + 1) * cell_px]
            out[r, c] = blk.mean() if blk.size else 0.0
    return out


def scale_samples(persons: list[Person]) -> list[tuple[float, float, float]]:
    """(x, y, meters-per-pixel) at each usable person's foot point.

    Only upright detections serve as rulers: a lying or seated person's box
    height is their body width, which would corrupt the calibration.
    """
    out = []
    for p in persons:
        if p.height_px < MIN_BOX_PX:
            continue
        width = p.box[2] - p.box[0]
        if width / p.height_px > MAX_RULER_ASPECT:
            continue
        out.append((p.foot[0], p.foot[1], REF_HEIGHT_M / p.height_px))
    return out


def cell_areas_px(frame_shape: tuple[int, ...], cell_px: int) -> np.ndarray:
    """True pixel area of each grid cell (edge cells are partial)."""
    h, w = frame_shape[0], frame_shape[1]
    rows, cols = grid_shape(frame_shape, cell_px)
    heights = np.minimum(cell_px, h - np.arange(rows) * cell_px).clip(min=1)
    widths = np.minimum(cell_px, w - np.arange(cols) * cell_px).clip(min=1)
    return np.outer(heights, widths).astype(np.float64)


def mpp_grid(
    persons: list[Person],
    distance: np.ndarray | None,
    frame_shape: tuple[int, ...],
    cell_px: int,
) -> np.ndarray:
    """Meters-per-pixel for every grid cell.

    With a distance map: fit the single pinhole scale `a` in mpp = a * distance
    from person-height samples (median ratio), then apply per cell. Without a
    map: inverse-distance-weighted interpolation of the sparse samples.
    Returns zeros when there are no usable samples.
    """
    gshape = grid_shape(frame_shape, cell_px)
    samples = scale_samples(persons)
    if not samples:
        return np.zeros(gshape, dtype=np.float64)

    if distance is not None:
        d_cells = block_mean(distance, cell_px, gshape)
        ratios = []
        for x, y, mpp in samples:
            yi = min(max(int(y), 0), distance.shape[0] - 1)
            xi = min(max(int(x), 0), distance.shape[1] - 1)
            d = float(distance[yi, xi])
            if d > 1e-6:
                ratios.append(mpp / d)
        if ratios:
            a = float(np.median(ratios))
            return a * d_cells

    # Fallback: inverse-distance-weighted interpolation of sparse samples.
    rows, cols = gshape
    cy = (np.arange(rows) + 0.5) * cell_px
    cx = (np.arange(cols) + 0.5) * cell_px
    gx, gy = np.meshgrid(cx, cy)
    num = np.zeros(gshape, dtype=np.float64)
    den = np.zeros(gshape, dtype=np.float64)
    for x, y, mpp in samples:
        w = 1.0 / ((gx - x) ** 2 + (gy - y) ** 2 + cell_px**2)
        num += w * mpp
        den += w
    return num / den


def gaussian_kernel_1d(sigma: float) -> np.ndarray:
    radius = max(1, int(round(3 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-(x**2) / (2 * sigma**2))
    return k / k.sum()


def smooth_grid(grid: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur with edge padding (mass-preserving-ish)."""
    if sigma <= 0:
        return grid
    k = gaussian_kernel_1d(sigma)
    radius = len(k) // 2
    padded = np.pad(grid, ((radius, radius), (0, 0)), mode="edge")
    rows = np.apply_along_axis(lambda col: np.convolve(col, k, mode="valid"), 0, padded)
    padded = np.pad(rows, ((0, 0), (radius, radius)), mode="edge")
    return np.apply_along_axis(lambda row: np.convolve(row, k, mode="valid"), 1, padded)


class DensityEstimator:
    """Stateful per-frame density estimation with temporal smoothing."""

    def __init__(self, cell_px: int = 48, ema_alpha: float = 0.45, smooth_sigma: float = 0.8):
        self.cell_px = cell_px
        self.ema_alpha = ema_alpha
        self.smooth_sigma = smooth_sigma
        self._ema: np.ndarray | None = None
        self._last_mpp: np.ndarray | None = None

    def update(
        self,
        persons: list[Person],
        distance: np.ndarray | None,
        frame_shape: tuple[int, ...],
    ) -> DensityGrid:
        gshape = grid_shape(frame_shape, self.cell_px)
        counts = np.zeros(gshape, dtype=np.float64)
        for p in persons:
            r, c = cell_of(*p.foot, self.cell_px, gshape)
            counts[r, c] += 1.0

        mpp = mpp_grid(persons, distance, frame_shape, self.cell_px)
        if mpp.any():
            self._last_mpp = mpp
        elif self._last_mpp is not None and self._last_mpp.shape == gshape:
            # No upright ruler this frame (e.g. everyone is down): keep the
            # previous calibration instead of zeroing the density map.
            mpp = self._last_mpp
        cell_area = cell_areas_px(frame_shape, self.cell_px) * mpp**2  # m^2 per cell
        density = np.zeros(gshape, dtype=np.float64)
        valid = cell_area > 1e-9
        density[valid] = counts[valid] / cell_area[valid]
        density = smooth_grid(density, self.smooth_sigma)

        if self._ema is None or self._ema.shape != density.shape:
            self._ema = density
        else:
            self._ema = self.ema_alpha * density + (1 - self.ema_alpha) * self._ema

        return DensityGrid(density=self._ema.copy(), counts=counts, mpp=mpp, cell_px=self.cell_px)
