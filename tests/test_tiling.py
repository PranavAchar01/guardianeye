"""Sliced inference: tile geometry, cross-tile NMS, and greedy ID tracking."""

import numpy as np

from guardianeye.detection import Person, SimpleTracker, merge_nms, tile_rects


def test_tile_rects_cover_frame_with_overlap():
    rects = tile_rects((1920, 1080), rows=3, cols=2, overlap=0.15)
    assert len(rects) == 6
    xs = [r[0] for r in rects] + [r[2] for r in rects]
    ys = [r[1] for r in rects] + [r[3] for r in rects]
    assert min(xs) == 0 and max(xs) == 1080
    assert min(ys) == 0 and max(ys) == 1920
    # interior tiles extend past the plain grid line: overlap exists
    x0, y0, x1, y1 = rects[3]  # row 1, col 1
    assert y0 < 640 and x0 < 540


def test_tile_rects_single_tile_is_whole_frame():
    assert tile_rects((240, 320), 1, 1) == [(0, 0, 320, 240)]


def test_merge_nms_dedupes_overlap_duplicates():
    boxes = np.array(
        [
            [100, 100, 120, 140],  # person A, tile 1
            [101, 101, 121, 141],  # person A again, seen by tile 2's overlap
            [300, 300, 320, 340],  # person B
        ],
        dtype=np.float32,
    )
    confs = np.array([0.9, 0.7, 0.8], dtype=np.float32)
    keep = merge_nms(boxes, confs)
    assert sorted(keep.tolist()) == [0, 2]


def person(cx, cy, conf=0.9):
    return Person(box=(cx - 5, cy - 15, cx + 5, cy + 15), conf=conf)


def test_simple_tracker_keeps_id_across_small_motion():
    tr = SimpleTracker()
    first = tr.update([person(100, 100)])
    second = tr.update([person(104, 102)])
    assert first[0].track_id == second[0].track_id


def test_simple_tracker_new_id_for_distant_detection():
    tr = SimpleTracker(max_dist_px=30)
    a = tr.update([person(100, 100)])
    b = tr.update([person(400, 400)])
    assert a[0].track_id != b[0].track_id


def test_simple_tracker_never_shares_an_id_in_one_frame():
    tr = SimpleTracker()
    tr.update([person(100, 100)])
    out = tr.update([person(102, 100), person(106, 100)])
    ids = [p.track_id for p in out]
    assert len(set(ids)) == 2
