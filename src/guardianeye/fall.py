"""Collapse detection: pose-based posture classification + down-time tracking.

A collapse is a person whose torso goes horizontal and stays down. Posture
comes from YOLO pose keypoints (shoulder-to-hip torso angle) with a
bounding-box aspect-ratio fallback when keypoints are occluded. An incident
is only *confirmed* after `confirm_s` seconds down, so someone bending over
or diving for a ball never pages the medics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .density import cell_of, grid_shape
from .detection import Person

POSTURE_STANDING = "standing"
POSTURE_LYING = "lying"
POSTURE_UNKNOWN = "unknown"

# COCO keypoint indices
L_SHOULDER, R_SHOULDER, L_HIP, R_HIP = 5, 6, 11, 12
KP_CONF = 0.3  # minimum keypoint confidence to trust
LYING_DEG = 55.0  # torso angle from vertical at/above which posture is lying
STANDING_DEG = 40.0  # at/below which posture is standing
MIN_TORSO_PX = 8.0  # shorter torsos are too degenerate to measure


def _torso_posture(person: Person) -> str:
    """Posture vote from keypoint torso angle; unknown when unusable."""
    kp = person.keypoints
    if kp is None:
        return POSTURE_UNKNOWN
    shoulders = [kp[i] for i in (L_SHOULDER, R_SHOULDER) if kp[i, 2] >= KP_CONF]
    hips = [kp[i] for i in (L_HIP, R_HIP) if kp[i, 2] >= KP_CONF]
    if not shoulders or not hips:
        return POSTURE_UNKNOWN
    sx = sum(p[0] for p in shoulders) / len(shoulders)
    sy = sum(p[1] for p in shoulders) / len(shoulders)
    hx = sum(p[0] for p in hips) / len(hips)
    hy = sum(p[1] for p in hips) / len(hips)
    dx, dy = hx - sx, hy - sy
    if math.hypot(dx, dy) < MIN_TORSO_PX:
        return POSTURE_UNKNOWN
    angle = math.degrees(math.atan2(abs(dx), abs(dy)))  # 0 deg = vertical
    if angle >= LYING_DEG:
        return POSTURE_LYING
    if angle <= STANDING_DEG:
        return POSTURE_STANDING
    return POSTURE_UNKNOWN


def posture_of(person: Person) -> str:
    """Classify one detection as standing / lying / unknown.

    Box aspect ratio is the primary signal: a genuinely standing person is
    never wider than tall, while perspective foreshortening routinely fools
    the keypoint torso angle on a person lying toward the camera. Keypoints
    decide only the ambiguous middle, and a keypoint "standing" vote that
    contradicts a wide box is treated as unknown rather than upright.
    """
    x1, y1, x2, y2 = person.box
    w, h = x2 - x1, y2 - y1
    if h <= 0:
        return POSTURE_UNKNOWN
    aspect = w / h
    if aspect >= 1.25:
        return POSTURE_LYING

    torso = _torso_posture(person)
    if torso == POSTURE_LYING:
        return POSTURE_LYING
    if torso == POSTURE_STANDING:
        return POSTURE_STANDING if aspect <= 1.05 else POSTURE_UNKNOWN
    if aspect <= 0.85:
        return POSTURE_STANDING
    return POSTURE_UNKNOWN


def _row_letters(r: int) -> str:
    """Spreadsheet-style row name: 0 -> A, 25 -> Z, 26 -> AA (never ambiguous)."""
    n = r + 1
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def zone_label(x: float, y: float, cell_px: int, frame_shape: tuple[int, ...]) -> str:
    """Human-radioable grid zone like 'B7' (rows lettered, columns numbered)."""
    gshape = grid_shape(frame_shape, cell_px)
    r, c = cell_of(x, y, cell_px, gshape)
    return f"{_row_letters(r)}{c + 1}"


@dataclass
class Incident:
    """One person-down episode.

    `end_t is None` means the incident was still open when the video ended
    ("ongoing"); `recovered` distinguishes a person seen upright again from a
    track that was simply lost (occlusion, carried away).
    """

    track_id: int
    start_t: float  # first lying observation of the streak
    zone: str
    location: tuple[float, float]
    confirmed_t: float | None = None
    end_t: float | None = None
    recovered: bool = False
    peak_down_s: float = 0.0

    @property
    def confirmed(self) -> bool:
        return self.confirmed_t is not None

    @property
    def active(self) -> bool:
        return self.confirmed and self.end_t is None


@dataclass
class _TrackState:
    lying_frames: int = 0
    upright_frames: int = 0
    streak_start_t: float | None = None
    incident: Incident | None = None
    last_seen: int = 0


@dataclass
class FallMonitor:
    """Per-track state machine turning posture streams into incidents."""

    fps: float
    confirm_s: float = 2.0  # continuous down-time before an incident confirms
    release_s: float = 0.7  # continuous upright time before an incident closes
    cell_px: int = 48
    episodes: list[Incident] = field(default_factory=list)
    _tracks: dict[int, _TrackState] = field(default_factory=dict)

    def update(
        self,
        persons: list[Person],
        frame_idx: int,
        t: float,
        frame_shape: tuple[int, ...],
    ) -> list[Incident]:
        """Feed one frame of detections; returns currently active incidents."""
        release_frames = max(1, int(self.release_s * self.fps))
        # Confirmation needs real lying evidence, not just elapsed time, so a
        # single misclassified frame can't age into an incident on its own.
        min_lying_frames = max(2, int(0.3 * self.confirm_s * self.fps))
        for p in persons:
            if p.track_id is None:
                continue
            st = self._tracks.setdefault(p.track_id, _TrackState())
            st.last_seen = frame_idx
            pos = posture_of(p)
            if pos == POSTURE_LYING:
                if st.streak_start_t is None:
                    st.streak_start_t = t
                st.lying_frames += 1
                st.upright_frames = 0
            elif pos == POSTURE_STANDING:
                st.upright_frames += 1
                if st.upright_frames >= release_frames:
                    if st.incident is not None:
                        st.incident.end_t = t
                        st.incident.recovered = True
                        st.incident = None
                    st.lying_frames = 0
                    st.streak_start_t = None
            # POSTURE_UNKNOWN: hold current counters (occlusion tolerance)

            # Down-time is wall-clock since the streak began: posture noise
            # while someone is on the ground must not stall the clock.
            down_s = t - st.streak_start_t if st.streak_start_t is not None else 0.0
            x, y = p.foot
            if (
                st.incident is None
                and down_s >= self.confirm_s
                and st.lying_frames >= min_lying_frames
            ):
                inc = Incident(
                    track_id=p.track_id,
                    start_t=st.streak_start_t if st.streak_start_t is not None else t,
                    zone=zone_label(x, y, self.cell_px, frame_shape),
                    location=(x, y),
                    confirmed_t=t,
                )
                st.incident = inc
                self.episodes.append(inc)
            if st.incident is not None:
                st.incident.location = (x, y)
                st.incident.zone = zone_label(x, y, self.cell_px, frame_shape)
                st.incident.peak_down_s = max(st.incident.peak_down_s, down_s)

        # Expire tracks not seen for a while: an incident whose person the
        # tracker lost must not blare MEDICAL EMERGENCY forever, and stale
        # state must not accumulate over long videos.
        expire_frames = max(release_frames, int(2.0 * self.fps))
        for tid in [
            tid for tid, st in self._tracks.items() if frame_idx - st.last_seen > expire_frames
        ]:
            st = self._tracks.pop(tid)
            if st.incident is not None and st.incident.end_t is None:
                st.incident.end_t = t
                st.incident.recovered = False  # lost, not seen upright

        return [
            st.incident
            for st in self._tracks.values()
            if st.incident is not None and st.incident.active
        ]
