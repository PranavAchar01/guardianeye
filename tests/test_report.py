"""Report generation: metrics JSON and standalone HTML."""

import json

from guardianeye.report import sparkline_svg, write_metrics, write_report

SUMMARY = {
    "input": "demo/fall-01.mp4",
    "n_frames": 100,
    "fps": 30.0,
    "proc_fps": 12.5,
    "thresholds": [2.0, 3.5, 5.0],
    "depth_source": "sensor",
    "peak_count": 3,
    "peak_density": 4.2,
    "worst_level": 3,
    "alerts": [{"start_t": 1.0, "end_t": 2.5, "peak_density": 5.6}],
    "incidents": [
        {
            "track_id": 4,
            "start_t": 2.0,
            "confirmed_t": 4.0,
            "end_t": None,
            "recovered": False,
            "zone": "B3",
            "peak_down_s": 3.1,
        },
        {
            "track_id": 7,
            "start_t": 0.5,
            "confirmed_t": 1.5,
            "end_t": 2.5,
            "recovered": True,
            "zone": "A1",
            "peak_down_s": 1.8,
        },
    ],
    "frames": [
        {
            "frame": 0,
            "t": 0.0,
            "count": 2,
            "max_density": 1.0,
            "mean_density": 0.5,
            "level": 0,
            "incidents": 0,
            "zones": [],
        },
        {
            "frame": 1,
            "t": 0.033,
            "count": 3,
            "max_density": 4.2,
            "mean_density": 1.5,
            "level": 2,
            "incidents": 1,
            "zones": [],
        },
    ],
}


def test_sparkline_svg_shape():
    svg = sparkline_svg([1.0, 2.0, 3.0], label="count")
    assert svg.startswith("<svg")
    assert "polyline" in svg
    assert "count" in svg


def test_sparkline_empty():
    assert sparkline_svg([]) == "<svg></svg>"


def test_metrics_roundtrip(tmp_path):
    p = tmp_path / "metrics.json"
    write_metrics(p, SUMMARY)
    assert json.loads(p.read_text())["peak_count"] == 3


def test_report_contains_key_sections(tmp_path):
    p = tmp_path / "report.html"
    write_report(p, SUMMARY, "annotated.mp4")
    html = p.read_text()
    assert "GuardianEye" in html
    assert "annotated.mp4" in html
    assert "B3" in html  # incident zone
    assert "ongoing at video end" in html  # open incident is never "recovered"
    assert "recovered 2.5s" in html  # closed incident shows recovery time
    assert "5.6" in html  # crush episode peak
    assert "CRITICAL" in html  # worst level


def test_report_empty_tables(tmp_path):
    summary = dict(SUMMARY, alerts=[], incidents=[], worst_level=0)
    p = tmp_path / "report.html"
    write_report(p, summary, "annotated.mp4")
    html = p.read_text()
    assert "No person-down incidents detected" in html
    assert "No crush episodes detected" in html
