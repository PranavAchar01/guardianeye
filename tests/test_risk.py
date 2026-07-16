"""Risk classification, zones, stagnation escalation, alert hysteresis."""

import numpy as np

from guardianeye.risk import (
    DEFAULT_THRESHOLDS,
    AlertTracker,
    classify,
    escalate_stagnation,
    find_zones,
)


def test_classify_boundaries():
    d = np.array([[0.0, 2.0, 3.5, 5.0, 10.0]])
    assert classify(d, DEFAULT_THRESHOLDS).tolist() == [[0, 1, 2, 3, 3]]


def test_escalate_stagnation_only_when_dense_and_slow():
    density = np.array([[4.5, 4.5, 1.0]])
    levels = classify(density, DEFAULT_THRESHOLDS)  # [[2, 2, 0]]
    speeds = {(0, 0): [0.1, 0.05], (0, 1): [1.2], (0, 2): [0.05]}
    out = escalate_stagnation(levels, density, speeds)
    assert out.tolist() == [[3, 2, 0]]  # slow+dense escalates; fast or sparse don't


def test_find_zones_connectivity_and_ordering():
    levels = np.array(
        [
            [2, 2, 0, 0],
            [0, 0, 0, 3],
            [0, 0, 0, 3],
        ]
    )
    density = np.array(
        [
            [4.0, 4.2, 0.0, 0.0],
            [0.0, 0.0, 0.0, 6.5],
            [0.0, 0.0, 0.0, 6.0],
        ]
    )
    zones = find_zones(levels, density, cell_px=48)
    assert len(zones) == 2
    assert zones[0].peak_density == 6.5  # densest zone is Z1
    assert zones[0].level == 3
    assert len(zones[0].cells) == 2
    assert len(zones[1].cells) == 2


def test_alert_tracker_hysteresis():
    at = AlertTracker(fire_after=3, clear_after=2)
    fps_t = [i / 10 for i in range(100)]
    # two hot frames: not enough to fire
    assert at.update(3, 6.0, fps_t[0]) is False
    assert at.update(3, 6.0, fps_t[1]) is False
    assert at.update(0, 1.0, fps_t[2]) is False
    # three consecutive hot frames: fires
    assert at.update(3, 6.0, fps_t[3]) is False
    assert at.update(3, 6.5, fps_t[4]) is False
    assert at.update(3, 7.0, fps_t[5]) is True
    # one cold frame doesn't clear
    assert at.update(0, 1.0, fps_t[6]) is True
    assert at.update(3, 6.0, fps_t[7]) is True
    # two consecutive cold frames clear and record the episode
    assert at.update(0, 1.0, fps_t[8]) is True
    assert at.update(0, 1.0, fps_t[9]) is False
    assert len(at.episodes) == 1
    ep = at.episodes[0]
    assert ep.peak_density == 7.0
    assert ep.start_t == fps_t[5]


def test_alert_tracker_finalize_closes_active_episode():
    at = AlertTracker(fire_after=1, clear_after=5)
    at.update(3, 6.0, 0.0)
    at.finalize(2.0)
    assert len(at.episodes) == 1
    assert at.episodes[0].end_t == 2.0
