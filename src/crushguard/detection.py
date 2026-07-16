"""YOLO person detection and multi-object tracking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Person:
    """A detected person in one frame."""

    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    conf: float
    track_id: int | None = None

    @property
    def foot(self) -> tuple[float, float]:
        """Ground-contact point: bottom-center of the box."""
        x1, _, x2, y2 = self.box
        return ((x1 + x2) / 2.0, y2)

    @property
    def height_px(self) -> float:
        return max(self.box[3] - self.box[1], 1.0)


class PersonDetector:
    """Ultralytics YOLO wrapper returning tracked person detections."""

    def __init__(self, weights: str = "yolo11n.pt", conf: float = 0.35, device: str = "cpu"):
        from ultralytics import YOLO  # deferred: heavy import

        self.model = YOLO(weights)
        self.conf = conf
        self.device = device

    def track(self, frame_bgr: np.ndarray) -> list[Person]:
        results = self.model.track(
            frame_bgr,
            persist=True,
            classes=[0],  # COCO class 0: person
            conf=self.conf,
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
        return [
            Person(
                box=(float(b[0]), float(b[1]), float(b[2]), float(b[3])), conf=float(c), track_id=i
            )
            for b, c, i in zip(boxes, confs, ids, strict=True)
        ]
