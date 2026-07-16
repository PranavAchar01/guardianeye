"""Collapse detection: posture classification and the incident state machine."""

import numpy as np

from guardianeye.detection import Person
from guardianeye.fall import (
    POSTURE_LYING,
    POSTURE_STANDING,
    POSTURE_UNKNOWN,
    FallMonitor,
    posture_of,
    zone_label,
)

FRAME_SHAPE = (240, 320)


def kp_person(sx, sy, hx, hy, box=(0, 0, 50, 100), tid=1) -> Person:
    """Person with synthetic shoulder/hip keypoints (both sides identical)."""
    kp = np.zeros((17, 3), dtype=np.float32)
    for i in (5, 6):
        kp[i] = (sx, sy, 0.9)
    for i in (11, 12):
        kp[i] = (hx, hy, 0.9)
    return Person(box=box, conf=0.9, track_id=tid, keypoints=kp)


def box_person(w, h, tid=1) -> Person:
    return Person(box=(0, 0, w, h), conf=0.9, track_id=tid)


def test_posture_vertical_torso_is_standing():
    assert posture_of(kp_person(50, 20, 50, 80)) == POSTURE_STANDING


def test_posture_horizontal_torso_is_lying():
    assert posture_of(kp_person(20, 50, 80, 50)) == POSTURE_LYING


def test_posture_low_conf_keypoints_fall_back_to_aspect():
    kp = np.zeros((17, 3), dtype=np.float32)  # all confidences below threshold
    wide = Person(box=(0, 0, 100, 40), conf=0.9, track_id=1, keypoints=kp)
    tall = Person(box=(0, 0, 40, 100), conf=0.9, track_id=1, keypoints=kp)
    assert posture_of(wide) == POSTURE_LYING
    assert posture_of(tall) == POSTURE_STANDING


def test_posture_ambiguous_aspect_is_unknown():
    assert posture_of(box_person(50, 50)) == POSTURE_UNKNOWN


def test_zone_label():
    assert zone_label(0, 0, 48, FRAME_SHAPE) == "A1"
    assert zone_label(300, 200, 48, FRAME_SHAPE) == "E7"


def _feed(monitor, person, n, start_frame, fps):
    incidents = []
    for k in range(n):
        f = start_frame + k
        incidents = monitor.update([person], f, f / fps, FRAME_SHAPE)
    return incidents, start_frame + n


def test_incident_confirms_after_sustained_down():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=1.0)
    lying = kp_person(20, 50, 80, 50)
    active, nxt = _feed(mon, lying, 29, 0, fps)
    assert active == []  # 29 frames < 1s: not confirmed yet
    active, nxt = _feed(mon, lying, 2, nxt, fps)
    assert len(active) == 1
    assert active[0].confirmed
    assert active[0].zone  # localized to a radioable zone


def test_brief_stumble_never_confirms():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=2.0, release_s=0.1)
    lying = kp_person(20, 50, 80, 50)
    standing = kp_person(50, 20, 50, 80)
    active, nxt = _feed(mon, lying, 20, 0, fps)  # down only 0.66s
    assert active == []
    active, nxt = _feed(mon, standing, 10, nxt, fps)
    assert active == []
    assert mon.episodes == []


def test_incident_closes_on_recovery_and_is_recorded():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=0.5, release_s=0.2)
    lying = kp_person(20, 50, 80, 50)
    standing = kp_person(50, 20, 50, 80)
    active, nxt = _feed(mon, lying, 30, 0, fps)
    assert len(active) == 1
    active, nxt = _feed(mon, standing, 10, nxt, fps)
    assert active == []
    assert len(mon.episodes) == 1
    ep = mon.episodes[0]
    assert ep.end_t is not None
    assert ep.peak_down_s >= 0.9


def test_occlusion_unknown_frames_hold_the_streak():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=1.0)
    lying = kp_person(20, 50, 80, 50)
    unknown = box_person(50, 50)  # ambiguous: must not reset the down-streak
    _feed(mon, lying, 25, 0, fps)
    _feed(mon, unknown, 10, 25, fps)
    active, _ = _feed(mon, lying, 6, 35, fps)
    assert len(active) == 1  # 25 + 6 lying frames > 1s despite unknown gap


def test_finalize_closes_open_incidents():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=0.5)
    lying = kp_person(20, 50, 80, 50)
    _feed(mon, lying, 30, 0, fps)
    mon.finalize(1.0)
    assert len(mon.episodes) == 1
    assert mon.episodes[0].end_t == 1.0
