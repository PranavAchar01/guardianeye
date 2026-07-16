"""Density math: scale calibration and people-per-m^2 on synthetic scenes."""

import numpy as np
import pytest

from guardianeye.density import (
    DensityEstimator,
    block_mean,
    cell_of,
    grid_shape,
    mpp_grid,
    scale_samples,
    smooth_grid,
)
from guardianeye.detection import Person


def person_at(x: float, foot_y: float, h_px: float, tid: int | None = None) -> Person:
    return Person(box=(x - 10, foot_y - h_px, x + 10, foot_y), conf=0.9, track_id=tid)


def test_grid_shape_and_cell_mapping():
    assert grid_shape((576, 768), 48) == (12, 16)
    assert cell_of(0, 0, 48, (12, 16)) == (0, 0)
    assert cell_of(767, 575, 48, (12, 16)) == (11, 15)
    # out-of-frame points clamp instead of crashing
    assert cell_of(-5, 9999, 48, (12, 16)) == (11, 0)


def test_scale_samples_skip_tiny_boxes():
    persons = [person_at(100, 100, 85.0), person_at(200, 200, 4.0)]
    samples = scale_samples(persons)
    assert len(samples) == 1
    x, y, mpp = samples[0]
    assert (x, y) == (100, 100)
    assert mpp == pytest.approx(1.7 / 85.0)


def test_mpp_grid_uniform_depth_matches_median_sample():
    frame_shape = (576, 768)
    distance = np.ones(frame_shape, dtype=np.float32) * 3.0
    persons = [person_at(100, 100, 85.0), person_at(500, 400, 85.0)]
    mpp = mpp_grid(persons, distance, frame_shape, 48)
    # mpp = 1.7/85 = 0.02 everywhere since distance is uniform
    assert mpp.shape == (12, 16)
    assert np.allclose(mpp, 0.02, atol=1e-9)


def test_mpp_grid_scales_linearly_with_distance():
    frame_shape = (96, 96)
    distance = np.ones(frame_shape, dtype=np.float32)
    distance[48:, :] = 2.0  # bottom half twice as far
    persons = [person_at(48, 40, 85.0)]  # ruler in the near half
    mpp = mpp_grid(persons, distance, frame_shape, 48)
    assert mpp[0, 0] == pytest.approx(0.02, rel=1e-6)
    assert mpp[1, 0] == pytest.approx(0.04, rel=1e-6)


def test_mpp_grid_no_persons_returns_zeros():
    mpp = mpp_grid([], None, (576, 768), 48)
    assert mpp.shape == (12, 16)
    assert np.all(mpp == 0)


def test_density_known_scene():
    """4 people in one 48px cell at 0.02 m/px -> cell is 0.96m x 0.96m -> ~4.34 p/m^2."""
    est = DensityEstimator(cell_px=48, ema_alpha=1.0, smooth_sigma=0.0)
    persons = [person_at(20 + i * 5, 30, 85.0) for i in range(4)]
    distance = np.ones((576, 768), dtype=np.float32)
    grid = est.update(persons, distance, (576, 768))
    expected = 4 / (48 * 0.02) ** 2
    assert grid.counts[0, 0] == 4
    assert grid.density[0, 0] == pytest.approx(expected, rel=1e-6)
    assert grid.max_density == pytest.approx(expected, rel=1e-6)


def test_density_ema_smooths_over_time():
    est = DensityEstimator(cell_px=48, ema_alpha=0.5, smooth_sigma=0.0)
    persons = [person_at(20, 30, 85.0)]
    distance = np.ones((96, 96), dtype=np.float32)
    g1 = est.update(persons, distance, (96, 96))
    g2 = est.update([], distance, (96, 96))
    assert g2.density[0, 0] == pytest.approx(g1.density[0, 0] / 2, rel=1e-6)


def test_smooth_grid_preserves_total_mass_roughly():
    g = np.zeros((10, 10))
    g[5, 5] = 100.0
    s = smooth_grid(g, sigma=1.0)
    assert s.sum() == pytest.approx(100.0, rel=0.01)
    assert s[5, 5] < 100.0


def test_block_mean_partial_edge_cells():
    arr = np.arange(100, dtype=np.float64).reshape(10, 10)
    out = block_mean(arr, 6, (2, 2))
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(arr[:6, :6].mean())
    assert out[1, 1] == pytest.approx(arr[6:, 6:].mean())
