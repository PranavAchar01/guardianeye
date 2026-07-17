"""Command-line interface: `guardianeye <video> -o out/`."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .risk import DEFAULT_THRESHOLDS


def _parse_tiles(text: str | None) -> tuple[int, int] | None:
    if text is None:
        return None
    try:
        rows, cols = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise SystemExit(f"--tiles expects RxC, e.g. 3x2 (got {text!r})") from None
    if rows < 1 or cols < 1:
        raise SystemExit("--tiles values must be >= 1")
    return (rows, cols)


def _thresholds(text: str) -> tuple[float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 3 or sorted(parts) != parts:
        raise argparse.ArgumentTypeError("thresholds must be 3 ascending numbers, e.g. 2,3.5,5")
    return (parts[0], parts[1], parts[2])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="guardianeye",
        description="AI safety officer for stadium video: collapse detection "
        "(YOLO pose) + crowd-crush early warning (depth-calibrated density).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("input", type=Path, help="input video file")
    p.add_argument(
        "-o", "--outdir", type=Path, default=Path("out"), help="output directory (default: out/)"
    )
    p.add_argument(
        "--weights",
        default="yolo11n-pose.pt",
        help="YOLO weights; pose models enable posture-based collapse detection "
        "(default: yolo11n-pose.pt)",
    )
    p.add_argument("--conf", type=float, default=0.35, help="detection confidence (default 0.35)")
    p.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="YOLO inference size; larger recovers small/distant people (default 640)",
    )
    p.add_argument("--cell-px", type=int, default=48, help="density grid cell size in px")
    p.add_argument(
        "--depth-every", type=int, default=8, help="recompute depth every N frames (default 8)"
    )
    p.add_argument(
        "--depth-model",
        default="small",
        help="Depth Anything V2 size (small|base|large) or an explicit HF model "
        "id; large is the strongest (default: small)",
    )
    p.add_argument(
        "--no-depth",
        action="store_true",
        help="skip the depth model; calibrate scale from body heights only",
    )
    p.add_argument(
        "--sensor-depth",
        default="none",
        choices=["none", "left", "right"],
        help="pane holding real depth-sensor data in a side-by-side capture "
        "(e.g. Kinect recordings); replaces the monocular depth model",
    )
    p.add_argument(
        "--confirm-secs",
        type=float,
        default=2.0,
        help="continuous down-time before a medical incident confirms (default 2.0)",
    )
    p.add_argument(
        "--no-fall",
        action="store_true",
        help="disable collapse detection (use for dense-crowd cameras where "
        "posture evidence is unreliable; density monitoring still runs)",
    )
    p.add_argument(
        "--edge-watch",
        action="store_true",
        help="enable drop-edge fall-off risk tracking: hazard edges from depth "
        "discontinuities + per-person trajectory prediction (needs depth)",
    )
    p.add_argument(
        "--tiles",
        default=None,
        metavar="RxC",
        help="sliced inference grid, e.g. 3x2: detect per overlapping tile so "
        "small/distant people survive the inference resize (slower, thorough)",
    )
    p.add_argument(
        "--slowmo",
        type=float,
        default=1.0,
        help="slow the output video by this factor (e.g. 4 plays at 1/4 speed) "
        "so per-person annotations are readable frame by frame",
    )
    p.add_argument(
        "--crowd-model",
        type=Path,
        default=None,
        metavar="WEIGHTS.pth",
        help="CSRNet weights for density-map crowd counting (packed stands "
        "beyond per-person detection); see scripts/fetch_demo.sh",
    )
    p.add_argument(
        "--thresholds",
        type=_thresholds,
        default=DEFAULT_THRESHOLDS,
        metavar="T1,T2,T3",
        help="density level boundaries in people/m^2 "
        f"(default {','.join(str(t) for t in DEFAULT_THRESHOLDS)})",
    )
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    p.add_argument("--max-frames", type=int, default=None, help="process at most N frames")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    from .pipeline import PipelineConfig, main_from_cli  # deferred: heavy imports

    cfg = PipelineConfig(
        input=args.input,
        outdir=args.outdir,
        weights=args.weights,
        conf=args.conf,
        imgsz=args.imgsz,
        cell_px=args.cell_px,
        depth_every=args.depth_every,
        depth_model=args.depth_model,
        use_depth=not args.no_depth,
        sensor_depth=args.sensor_depth,
        thresholds=args.thresholds,
        device=args.device,
        max_frames=args.max_frames,
        confirm_s=args.confirm_secs,
        use_fall=not args.no_fall,
        edge_watch=args.edge_watch,
        crowd_model=args.crowd_model,
        tiles=_parse_tiles(args.tiles),
        slowmo=args.slowmo,
    )
    main_from_cli(cfg)


if __name__ == "__main__":
    main()
