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


def test_posture_no_keypoints_needs_stronger_aspect_evidence():
    # 1.4 aspect: lying with keypoints present, unknown without (occluded
    # torsos in crowds produce wide boxes on detect-only weights).
    kp = np.zeros((17, 3), dtype=np.float32)
    with_kp = Person(box=(0, 0, 70, 50), conf=0.9, track_id=1, keypoints=kp)
    without_kp = Person(box=(0, 0, 70, 50), conf=0.9, track_id=1)
    assert posture_of(with_kp) == POSTURE_LYING
    assert posture_of(without_kp) == POSTURE_UNKNOWN
    wide_enough = Person(box=(0, 0, 100, 50), conf=0.9, track_id=1)
    assert posture_of(wide_enough) == POSTURE_LYING


def test_posture_bottom_clipped_box_never_lying_without_keypoints():
    clipped = Person(box=(0, 190, 100, 239), conf=0.9, track_id=1)  # feet cut off
    assert posture_of(clipped, FRAME_SHAPE) == POSTURE_UNKNOWN
    mid_frame = Person(box=(0, 100, 100, 149), conf=0.9, track_id=1)
    assert posture_of(mid_frame, FRAME_SHAPE) == POSTURE_LYING


def test_zone_label():
    assert zone_label(0, 0, 48, FRAME_SHAPE) == "A1"
    assert zone_label(300, 200, 48, FRAME_SHAPE) == "E7"


def test_zone_label_rows_never_wrap_ambiguously():
    tall = (2160, 3840)  # 4K portrait-ish: 45 grid rows
    assert zone_label(0, 26 * 48 + 1, 48, tall) == "AA1"
    assert zone_label(0, 27 * 48 + 1, 48, tall) == "AB1"


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
    assert ep.recovered is True
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


def test_incident_still_open_at_video_end_stays_ongoing():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=0.5)
    lying = kp_person(20, 50, 80, 50)
    active, _ = _feed(mon, lying, 30, 0, fps)
    assert len(active) == 1
    assert len(mon.episodes) == 1
    # Never stamp a recovery the camera didn't see.
    assert mon.episodes[0].end_t is None
    assert mon.episodes[0].recovered is False


def test_lost_track_expires_incident_as_not_recovered():
    fps = 30.0
    mon = FallMonitor(fps=fps, confirm_s=0.5, release_s=0.2)
    lying = kp_person(20, 50, 80, 50, tid=1)
    other = kp_person(50, 20, 50, 80, tid=2)  # unrelated standing person
    active, nxt = _feed(mon, lying, 30, 0, fps)
    assert len(active) == 1
    # Track 1 vanishes; only track 2 is seen for well past the expiry window.
    for k in range(90):
        f = nxt + k
        active = mon.update([other], f, f / fps, FRAME_SHAPE)
    assert active == []  # no eternal MEDICAL EMERGENCY from a lost track
    assert len(mon.episodes) == 1
    ep = mon.episodes[0]
    assert ep.end_t is not None
    assert ep.recovered is False
