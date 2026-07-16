"""Edge-fall risk: cliff detection, proximity, and trajectory prediction."""

import numpy as np

from guardianeye.detection import Person
from guardianeye.edge import (
    EDGE_FALL_RISK,
    EDGE_NEAR,
    EdgeMonitor,
    hazard_mask,
)

FRAME_SHAPE = (240, 320)
FPS = 30.0


def cliff_scene() -> np.ndarray:
    """Relative-distance map: near platform (2.0) with a drop (8.0) at x>=200."""
    d = np.full(FRAME_SHAPE, 2.0, dtype=np.float32)
    d[:, 200:] = 8.0
    return d


def person_at(x: float, y: float, tid: int = 1) -> Person:
    return Person(box=(x - 8, y - 40, x + 8, y), conf=0.9, track_id=tid)


def test_hazard_mask_marks_the_cliff_line_only():
    mask = hazard_mask(cliff_scene())
    assert mask[:, 199:201].all()  # the discontinuity is hazardous
    assert not mask[:, :190].any()  # flat platform is safe
    assert not mask[:, 210:].any()  # flat lower ground is safe


def test_standing_far_from_edge_is_safe():
    mon = EdgeMonitor(fps=FPS)
    statuses, mask = mon.update([person_at(60, 120)], cliff_scene(), 0, 0.0, FRAME_SHAPE)
    assert statuses == []
    assert mask is not None


def test_standing_at_the_edge_is_near():
    mon = EdgeMonitor(fps=FPS)
    statuses, _ = mon.update([person_at(192, 120)], cliff_scene(), 0, 0.0, FRAME_SHAPE)
    assert len(statuses) == 1
    assert statuses[0].level == EDGE_NEAR
    assert statuses[0].zone


def test_walking_toward_edge_predicts_fall_risk_with_tte():
    mon = EdgeMonitor(fps=FPS, confirm_frames=2)
    d = cliff_scene()
    # Walk right at ~60 px/s from x=140: crosses the cliff at x=200 in ~1s.
    statuses = []
    for i in range(8):
        x = 140 + i * 2.0  # 2 px/frame * 30 fps = 60 px/s
        statuses, _ = mon.update([person_at(x, 120)], d, i, i / FPS, FRAME_SHAPE)
    assert len(statuses) == 1
    st = statuses[0]
    assert st.level == EDGE_FALL_RISK
    assert st.tte_s is not None and 0.3 <= st.tte_s <= 1.5
    assert len(mon.events) == 1  # confirmed once, not once per frame
    assert mon.events[0].min_tte_s is not None


def test_walking_parallel_to_edge_is_not_fall_risk():
    mon = EdgeMonitor(fps=FPS)
    d = cliff_scene()
    statuses = []
    for i in range(8):
        y = 60 + i * 2.0  # moving straight down, x=100 stays far from cliff
        statuses, _ = mon.update([person_at(100, y)], d, i, i / FPS, FRAME_SHAPE)
    assert statuses == []


def test_no_depth_means_no_edge_analysis():
    mon = EdgeMonitor(fps=FPS)
    statuses, mask = mon.update([person_at(192, 120)], None, 0, 0.0, FRAME_SHAPE)
    assert statuses == [] and mask is None


def test_stationary_person_at_edge_never_logs_fall_event():
    mon = EdgeMonitor(fps=FPS, confirm_frames=2)
    d = cliff_scene()
    for i in range(10):
        mon.update([person_at(192, 120)], d, i, i / FPS, FRAME_SHAPE)
    assert mon.events == []


def test_global_flow_recovers_camera_shift():
    import cv2

    from guardianeye.edge import global_flow

    rng = np.random.default_rng(7)
    base = cv2.GaussianBlur((rng.random((240, 320)) * 255).astype(np.uint8), (9, 9), 3)
    shifted = np.roll(base, (3, 6), axis=(0, 1))  # camera moved by (+6, +3) px
    dx, dy = global_flow(base, shifted)
    assert abs(dx - 6) <= 1.0
    assert abs(dy - 3) <= 1.0


def test_camera_pan_toward_edge_is_not_fall_risk():
    """World-static person during a camera pan must not read as walking."""
    mon = EdgeMonitor(fps=FPS, confirm_frames=2)
    d = cliff_scene()
    statuses = []
    for i in range(10):
        # Scene (and person) drift +4 px/frame in pixel space; ego-motion
        # tracking has measured the same camera shift.
        mon._cam_x = 4.0 * i
        statuses, _ = mon.update([person_at(140 + 4.0 * i, 120)], d, i, i / FPS, FRAME_SHAPE)
    assert all(s.level < EDGE_FALL_RISK for s in statuses)
    assert mon.events == []
