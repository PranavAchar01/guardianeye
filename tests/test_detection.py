"""Track-ID stitching for detections the tracker dropped."""

from guardianeye.detection import Person, stitch_ids


def anon(x, y):
    return Person(box=(x - 10, y - 40, x + 10, y), conf=0.8, track_id=None)


def test_stitch_inherits_nearby_lost_id():
    prev = {7: (100.0, 100.0, 41)}
    out = stitch_ids([anon(105, 103)], prev)
    assert out[0].track_id == 7


def test_stitch_ignores_far_detections():
    prev = {7: (100.0, 100.0, 41)}
    out = stitch_ids([anon(300, 300)], prev)
    assert out[0].track_id is None


def test_stitch_never_steals_an_active_id():
    prev = {7: (100.0, 100.0, 41)}
    tracked = Person(box=(90, 60, 110, 100), conf=0.9, track_id=7)
    out = stitch_ids([tracked, anon(105, 103)], prev)
    assert out[0].track_id == 7
    assert out[1].track_id is None  # id 7 already in use this frame


def test_stitch_assigns_each_id_once():
    prev = {7: (100.0, 100.0, 41)}
    out = stitch_ids([anon(102, 101), anon(104, 99)], prev)
    ids = [p.track_id for p in out]
    assert ids.count(7) == 1


def test_stitch_prefers_nearest():
    prev = {1: (100.0, 100.0, 40), 2: (140.0, 100.0, 40)}
    out = stitch_ids([anon(130, 100)], prev)
    assert out[0].track_id == 2
