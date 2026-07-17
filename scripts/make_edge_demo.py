"""Assemble the Edge Watch demo: drone footage + fall-off risk tracking.

Usage: uv run python scripts/make_edge_demo.py
Input:  out/drone/annotated.mp4 (see DEMO.md for the processing command)
Output: out/edge-demo.mp4 (1280x720, 30 fps, H.264)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_showcase import DIM, FG, RED, card, card_segment, run, video_segment  # noqa: E402


def main() -> None:
    out = Path("out")
    work = out / "edge_parts"
    work.mkdir(parents=True, exist_ok=True)
    src = out / "drone" / "annotated.mp4"
    if not src.exists():
        sys.exit(f"missing {src}; run the edge-watch demo command in DEMO.md first")

    card(
        work / "c1.png",
        [
            ("GUARDIANEYE  //  EDGE WATCH", 66, FG, True),
            ("Will anyone fall off?", 40, RED, False),
            ("", 18, FG, False),
            ("Drone above the stadium  ·  depth-cliff hazard map", 28, DIM, False),
            ("ego-motion-compensated tracking  ·  time-to-edge prediction", 28, DIM, False),
        ],
    )
    card(
        work / "c2.png",
        [
            ("Red lines are drop edges found in the depth map.", 34, FG, True),
            ("A sustained trajectory across one fires a zone alert", 30, DIM, False),
            ("before the fall, not after.", 30, DIM, False),
            ("", 16, FG, False),
            ("github.com/PranavAchar01/guardianeye", 28, RED, False),
        ],
    )

    card_segment(work / "c1.png", work / "s0.mp4", 4.0)
    video_segment(src, work / "s1.mp4")
    card_segment(work / "c2.png", work / "s2.mp4", 5.0)

    concat = work / "list.txt"
    concat.write_text("".join(f"file 's{i}.mp4'\n" for i in range(3)))
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out / "edge-demo.mp4"),
        ]
    )
    print(f"edge demo ready: {out / 'edge-demo.mp4'}")


if __name__ == "__main__":
    main()
