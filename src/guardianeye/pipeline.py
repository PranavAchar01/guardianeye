"""End-to-end video pipeline: detect -> depth -> density/fall -> risk -> render."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import __version__, density, render, report, risk
from .depth import split_sensor_frame
from .detection import PersonDetector, stitch_ids
from .fall import FallMonitor


@dataclass
class PipelineConfig:
    input: Path
    outdir: Path = Path("out")
    weights: str = "yolo11n-pose.pt"
    conf: float = 0.35
    imgsz: int = 640
    cell_px: int = 48
    depth_every: int = 8  # recompute the monocular depth map every N frames
    depth_model: str = "small"  # Depth Anything V2 size alias or HF model id
    use_depth: bool = True
    sensor_depth: str = "none"  # "left"/"right": pane of a side-by-side sensor capture
    thresholds: tuple[float, float, float] = risk.DEFAULT_THRESHOLDS
    device: str = "auto"
    max_frames: int | None = None
    ema_alpha: float = 0.45
    smooth_sigma: float = 0.8
    fire_after_s: float = 0.8  # sustained CRITICAL time before the crush alert fires
    clear_after_s: float = 1.2
    confirm_s: float = 2.0  # continuous down-time before a medical incident confirms
    use_fall: bool = True  # collapse detection; disable for dense-crowd cameras
    # where posture evidence is unreliable (density monitoring still runs)
    edge_watch: bool = False  # drop-edge fall-off risk (needs a depth channel)
    crowd_model: Path | None = None  # CSRNet weights: density-map counting for
    # packed crowds beyond per-person detection
    crowd_every: int = 4  # recompute the crowd count map every N frames
    tiles: tuple[int, int] | None = None  # sliced inference (rows, cols) so the
    # detector sees small/distant people at native resolution
    slowmo: float = 1.0  # write output at source_fps / slowmo (playback slowdown)


@dataclass
class FrameMetrics:
    frame: int
    t: float
    count: int
    max_density: float
    mean_density: float
    level: int
    incidents: int
    edge_risks: int = 0
    zones: list[dict] = field(default_factory=list)


def resolve_device(pref: str) -> str:
    if pref != "auto":
        return pref
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _h264_encode(raw: Path, final: Path) -> bool:
    """Re-encode to browser-playable H.264 if ffmpeg is available."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(raw),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(final),
        ],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def run(cfg: PipelineConfig) -> dict:
    cfg.outdir.mkdir(parents=True, exist_ok=True)
    # Record the exact settings this run used, so any output directory is
    # reproducible on its own without the original command line.
    run_config = asdict(cfg)
    run_config["guardianeye_version"] = __version__
    (cfg.outdir / "config.json").write_text(json.dumps(run_config, indent=2, default=str))
    device = resolve_device(cfg.device)
    print(f"[guardianeye] device={device} input={cfg.input}", flush=True)

    cap = cv2.VideoCapture(str(cfg.input))
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {cfg.input}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if cfg.sensor_depth in ("left", "right"):
        width = width // 2  # output is the RGB pane only
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if cfg.max_frames:
        total = min(total, cfg.max_frames)

    detector = PersonDetector(
        weights=cfg.weights, conf=cfg.conf, device=device, imgsz=cfg.imgsz, tiles=cfg.tiles
    )
    depth_estimator = None
    if cfg.use_depth and cfg.sensor_depth == "none":
        try:
            from .depth import DepthEstimator

            depth_estimator = DepthEstimator(device=device, model_id=cfg.depth_model)
        except Exception as e:  # noqa: BLE001 - degrade gracefully, keep processing
            print(
                f"[guardianeye] depth model unavailable ({e}); "
                "falling back to detection-only scale",
                flush=True,
            )

    estimator = density.DensityEstimator(
        cell_px=cfg.cell_px, ema_alpha=cfg.ema_alpha, smooth_sigma=cfg.smooth_sigma
    )
    crush_alerts = risk.AlertTracker(
        fire_after=max(1, int(cfg.fire_after_s * fps)),
        clear_after=max(1, int(cfg.clear_after_s * fps)),
    )
    falls = FallMonitor(fps=fps, confirm_s=cfg.confirm_s, cell_px=cfg.cell_px)
    edges = None
    if cfg.edge_watch:
        from .edge import EdgeMonitor

        edges = EdgeMonitor(fps=fps, cell_px=cfg.cell_px)
    crowd = None
    if cfg.crowd_model is not None:
        from .crowd import CrowdCounter

        crowd = CrowdCounter(str(cfg.crowd_model), device=device)

    raw_path = cfg.outdir / "annotated_raw.mp4"
    out_fps = max(fps / max(cfg.slowmo, 1.0), 1.0)  # slow playback, not skipped frames
    writer = cv2.VideoWriter(
        str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (width, height)
    )
    if not writer.isOpened():
        raise SystemExit(f"cannot open video writer: {raw_path}")

    distance: np.ndarray | None = None
    count_map: np.ndarray | None = None
    tracks_prev: dict[int, tuple[float, float, int]] = {}
    metrics: list[FrameMetrics] = []
    t_start = time.perf_counter()
    frame_idx = 0

    while True:
        if cfg.max_frames is not None and frame_idx >= cfg.max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_idx / fps

        if cfg.sensor_depth in ("left", "right"):
            frame, distance = split_sensor_frame(frame, cfg.sensor_depth)
        persons = stitch_ids(detector.track(frame), tracks_prev)
        if depth_estimator is not None and frame_idx % cfg.depth_every == 0:
            distance = depth_estimator.relative_distance(frame)
        if crowd is not None and frame_idx % cfg.crowd_every == 0:
            count_map = crowd.count_map(frame)
        people_n = int(round(float(count_map.sum()))) if count_map is not None else len(persons)

        grid = estimator.update(persons, distance, frame.shape, count_map=count_map)
        levels = risk.classify(grid.density, cfg.thresholds)
        cell_speeds = risk.speed_samples_ms(tracks_prev, persons, frame_idx, fps, grid)
        levels = risk.escalate_stagnation(
            levels,
            grid.density,
            cell_speeds,
            # keep the stagnation floor consistent with custom thresholds
            density_floor=(cfg.thresholds[1] + cfg.thresholds[2]) / 2,
        )
        zones = risk.find_zones(levels, grid.density, cfg.cell_px)
        incidents = falls.update(persons, frame_idx, t, frame.shape) if cfg.use_fall else []
        edge_statuses, edge_mask = (None, None)
        if edges is not None:
            edge_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edge_statuses, edge_mask = edges.update(
                persons, distance, frame_idx, t, frame.shape, edge_gray
            )
        frame_level = int(levels.max()) if levels.size else 0
        if incidents or any(s.level >= 2 for s in edge_statuses or []):
            frame_level = 3
        crush_on = crush_alerts.update(int(levels.max()) if levels.size else 0, grid.max_density, t)

        annotated = render.render_frame(
            frame,
            persons,
            grid,
            levels,
            zones,
            distance,
            cfg.thresholds,
            t,
            frame_idx,
            crush_on,
            incidents,
            edge_statuses,
            edge_mask,
            people_count=people_n,
        )
        writer.write(annotated)

        metrics.append(
            FrameMetrics(
                frame=frame_idx,
                t=round(t, 3),
                count=people_n,
                max_density=round(grid.max_density, 3),
                mean_density=round(grid.occupied_mean, 3),
                level=frame_level,
                incidents=len(incidents),
                edge_risks=len(edge_statuses or []),
                zones=[
                    {"id": z.zone_id, "level": z.level, "peak": round(z.peak_density, 2)}
                    for z in zones
                ],
            )
        )
        frame_idx += 1
        if frame_idx % 25 == 0 or frame_idx == total:
            el = time.perf_counter() - t_start
            print(
                f"[guardianeye] {frame_idx}/{total or '?'} frames  "
                f"people={people_n:4d}  peak={grid.max_density:4.1f} p/m2  "
                f"down={len(incidents)}  edge={len(edge_statuses or [])}  "
                f"({frame_idx / el:.1f} fps)",
                flush=True,
            )

    cap.release()
    writer.release()
    elapsed = time.perf_counter() - t_start
    last_t = metrics[-1].t if metrics else 0.0
    crush_alerts.finalize(last_t)
    # Incidents still open here stay end_t=None: a person still down when the
    # video ends must be reported as ongoing, never as recovered.

    final_path = cfg.outdir / "annotated.mp4"
    if _h264_encode(raw_path, final_path):
        raw_path.unlink()
    else:
        raw_path.rename(final_path)

    summary = {
        "input": str(cfg.input),
        "n_frames": len(metrics),
        "fps": fps,
        "proc_fps": len(metrics) / elapsed if elapsed > 0 else 0.0,
        "thresholds": list(cfg.thresholds),
        "depth_source": (
            "sensor"
            if cfg.sensor_depth in ("left", "right")
            else "monocular"
            if depth_estimator is not None
            else "none"
        ),
        "peak_count": max((m.count for m in metrics), default=0),
        "peak_density": max((m.max_density for m in metrics), default=0.0),
        "worst_level": max((m.level for m in metrics), default=0),
        "alerts": [
            {"start_t": a.start_t, "end_t": a.end_t, "peak_density": a.peak_density}
            for a in crush_alerts.episodes
        ],
        "incidents": [
            {
                "track_id": i.track_id,
                "start_t": round(i.start_t, 2),
                "confirmed_t": round(i.confirmed_t, 2) if i.confirmed_t is not None else None,
                "end_t": round(i.end_t, 2) if i.end_t is not None else None,
                "recovered": i.recovered,
                "zone": i.zone,
                "peak_down_s": round(i.peak_down_s, 2),
            }
            for i in falls.episodes
        ],
        "edge_events": [
            {
                "track_id": e.track_id,
                "start_t": round(e.start_t, 2),
                "zone": e.zone,
                "min_tte_s": round(e.min_tte_s, 2) if e.min_tte_s is not None else None,
            }
            for e in (edges.events if edges is not None else [])
        ],
        "frames": [vars(m) for m in metrics],
    }
    report.write_metrics(cfg.outdir / "metrics.json", summary)
    report.write_report(cfg.outdir / "report.html", summary, final_path.name)
    print(
        f"[guardianeye] done: {len(metrics)} frames in {elapsed:.1f}s "
        f"-> {final_path}, report.html, metrics.json",
        flush=True,
    )
    return summary


def main_from_cli(cfg: PipelineConfig) -> dict:
    try:
        return run(cfg)
    except KeyboardInterrupt:
        print("[guardianeye] interrupted", file=sys.stderr)
        raise SystemExit(130) from None
