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


def tile_rects(
    frame_shape: tuple[int, ...], rows: int, cols: int, overlap: float = 0.15
) -> list[tuple[int, int, int, int]]:
    """Overlapping tile rectangles (x0, y0, x1, y1) covering the frame.

    Slicing lets the detector see small/distant people at native resolution
    instead of shrinking the whole frame to the inference size (SAHI-style).
    """
    h, w = frame_shape[0], frame_shape[1]
    th, tw = h / rows, w / cols
    oy, ox = int(th * overlap), int(tw * overlap)
    rects = []
    for r in range(rows):
        for c in range(cols):
            y0 = max(int(r * th) - oy, 0)
            y1 = min(int((r + 1) * th) + oy, h)
            x0 = max(int(c * tw) - ox, 0)
            x1 = min(int((c + 1) * tw) + ox, w)
            rects.append((x0, y0, x1, y1))
    return rects


def merge_nms(boxes: np.ndarray, confs: np.ndarray, iou: float = 0.5) -> np.ndarray:
    """Indices to keep after cross-tile NMS (duplicates live in overlaps)."""
    import torch
    from torchvision.ops import nms

    keep = nms(
        torch.from_numpy(boxes.astype(np.float32)),
        torch.from_numpy(confs.astype(np.float32)),
        iou,
    )
    return keep.numpy()


class SimpleTracker:
    """Greedy nearest-neighbor ID assignment for tiled detections.

    ByteTrack can't run across independently-detected tiles, so tiled mode
    tracks by center proximity: confident detections claim the nearest
    previous-frame ID within `max_dist_px`; the rest get fresh IDs.
    """

    def __init__(self, max_dist_px: float = 48.0):
        self.max_dist_px = max_dist_px
        self._prev: dict[int, tuple[float, float]] = {}
        self._next_id = 1

    def update(self, persons: list[Person]) -> list[Person]:
        out: list[Person] = []
        new_prev: dict[int, tuple[float, float]] = {}
        used: set[int] = set()
        for p in sorted(persons, key=lambda q: q.conf, reverse=True):
            cx, cy = p.center
            best_id, best_d = None, self.max_dist_px
            for tid, (px, py) in self._prev.items():
                if tid in used:
                    continue
                d = float(np.hypot(cx - px, cy - py))
                if d < best_d:
                    best_id, best_d = tid, d
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
            used.add(best_id)
            new_prev[best_id] = (cx, cy)
            out.append(Person(box=p.box, conf=p.conf, track_id=best_id, keypoints=p.keypoints))
        self._prev = new_prev
        return out


class PersonDetector:
    """Ultralytics YOLO wrapper returning tracked person detections.

    Defaults to a pose model so downstream posture classification gets
    keypoints; plain detection weights also work (keypoints stay None).
    With `tiles=(rows, cols)` the frame is sliced into overlapping tiles so
    small/distant people survive the resize to the inference size.
    """

    def __init__(
        self,
        weights: str = "yolo11n-pose.pt",
        conf: float = 0.35,
        device: str = "cpu",
        imgsz: int = 640,
        tiles: tuple[int, int] | None = None,
    ):
        from ultralytics import YOLO  # deferred: heavy import

        self.model = YOLO(weights)
        self.conf = conf
        self.device = device
        self.imgsz = imgsz  # larger sizes recover small/distant people
        self.tiles = tiles
        self._tracker = SimpleTracker() if tiles else None

    def track(self, frame_bgr: np.ndarray) -> list[Person]:
        if self.tiles is not None:
            return self._track_tiled(frame_bgr)
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

    def _track_tiled(self, frame_bgr: np.ndarray) -> list[Person]:
        rows, cols = self.tiles  # type: ignore[misc]
        all_boxes, all_confs = [], []
        for x0, y0, x1, y1 in tile_rects(frame_bgr.shape, rows, cols):
            res = self.model.predict(
                frame_bgr[y0:y1, x0:x1],
                classes=[0],
                conf=self.conf,
                imgsz=self.imgsz,
                device=self.device,
                verbose=False,
                max_det=1500,
            )[0]
            if res.boxes is None or len(res.boxes) == 0:
                continue
            b = res.boxes.xyxy.cpu().numpy()
            b[:, [0, 2]] += x0
            b[:, [1, 3]] += y0
            all_boxes.append(b)
            all_confs.append(res.boxes.conf.cpu().numpy())
        if not all_boxes:
            return []
        boxes = np.concatenate(all_boxes)
        confs = np.concatenate(all_confs)
        keep = merge_nms(boxes, confs)
        persons = [
            Person(
                box=(
                    float(boxes[i][0]),
                    float(boxes[i][1]),
                    float(boxes[i][2]),
                    float(boxes[i][3]),
                ),
                conf=float(confs[i]),
            )
            for i in keep
        ]
        assert self._tracker is not None
        return self._tracker.update(persons)
