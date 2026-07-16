"""YOLO pose-model person detection and multi-object tracking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Person:
    """A detected person in one frame."""

    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    conf: float
    track_id: int | None = None
    keypoints: np.ndarray | None = None  # (17, 3) COCO keypoints: x, y, confidence

    @property
    def foot(self) -> tuple[float, float]:
        """Ground-contact point: bottom-center of the box."""
        x1, _, x2, y2 = self.box
        return ((x1 + x2) / 2.0, y2)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def height_px(self) -> float:
        return max(self.box[3] - self.box[1], 1.0)


def stitch_ids(
    persons: list[Person],
    prev_positions: dict[int, tuple[float, float, int]],
    max_dist_px: float = 64.0,
) -> list[Person]:
    """Re-attach IDs to detections the tracker dropped.

    Trackers routinely lose a person during a fall (sudden shape/motion
    change), which would reset any down-time accounting. A detection with no
    ID inherits the nearest recently-seen track position within
    `max_dist_px`, unless that ID is still in use this frame.
    """
    taken = {p.track_id for p in persons if p.track_id is not None}
    out: list[Person] = []
    for p in persons:
        if p.track_id is not None:
            out.append(p)
            continue
        x, y = p.foot
        best_id, best_d = None, max_dist_px
        for tid, (px, py, _) in prev_positions.items():
            if tid in taken:
                continue
            d = float(np.hypot(x - px, y - py))
            if d < best_d:
                best_id, best_d = tid, d
        if best_id is not None:
            taken.add(best_id)
            p = Person(box=p.box, conf=p.conf, track_id=best_id, keypoints=p.keypoints)
        out.append(p)
    return out


class PersonDetector:
    """Ultralytics YOLO wrapper returning tracked person detections.

    Defaults to a pose model so downstream posture classification gets
    keypoints; plain detection weights also work (keypoints stay None).
    """

    def __init__(
        self,
        weights: str = "yolo11n-pose.pt",
        conf: float = 0.35,
        device: str = "cpu",
        imgsz: int = 640,
    ):
        from ultralytics import YOLO  # deferred: heavy import

        self.model = YOLO(weights)
        self.conf = conf
        self.device = device
        self.imgsz = imgsz  # larger sizes recover small/distant people

    def track(self, frame_bgr: np.ndarray) -> list[Person]:
        results = self.model.track(
            frame_bgr,
            persist=True,
            classes=[0],  # COCO class 0: person
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return []
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        if r.boxes.id is not None:
            ids: list[int | None] = [int(i) for i in r.boxes.id.int().cpu().numpy()]
        else:
            ids = [None] * len(boxes)

        kpts: np.ndarray | None = None
        if r.keypoints is not None and r.keypoints.xy is not None and len(r.keypoints.xy):
            xy = r.keypoints.xy.cpu().numpy()  # (n, 17, 2)
            kc = r.keypoints.conf
            kconf = (
                kc.cpu().numpy()[..., None]
                if kc is not None
                else np.zeros((*xy.shape[:2], 1), dtype=np.float32)
            )
            kpts = np.concatenate([xy, kconf], axis=2)  # (n, 17, 3)

        return [
            Person(
                box=(float(b[0]), float(b[1]), float(b[2]), float(b[3])),
                conf=float(c),
                track_id=i,
                keypoints=kpts[n] if kpts is not None else None,
            )
            for n, (b, c, i) in enumerate(zip(boxes, confs, ids, strict=True))
        ]
