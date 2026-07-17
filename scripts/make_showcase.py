"""Assemble the GuardianEye showcase video: title cards + processed segments.

Usage: uv run python scripts/make_showcase.py
Inputs (produced by the demo commands in DEMO.md):
  out/morocco/annotated.mp4   crowd monitoring on packed-stadium footage
  out/fall01/annotated.mp4    collapse detection on a Kinect depth recording
Output: out/showcase.mp4 (1920x1080, 30 fps, H.264)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
SCALE = H / 720  # card text sizes below are specified in 720p units
BG = (14, 16, 20)
FG = (232, 232, 232)
DIM = (150, 155, 165)
RED = (235, 80, 80)
FONT = "/System/Library/Fonts/Helvetica.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, int(size * SCALE), index=1 if bold else 0)


def card(path: Path, lines: list[tuple[str, int, tuple[int, int, int], bool]]) -> None:
    """Render centered text lines: (text, size, color, bold)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 6, W, H], fill=RED)  # accent bar
    heights = []
    for text, size, _, bold in lines:
        box = d.textbbox((0, 0), text, font=font(size, bold))
        heights.append(box[3] - box[1] + int(size * SCALE * 0.55))
    y = (H - sum(heights)) // 2
    for (text, size, color, bold), lh in zip(lines, heights, strict=True):
        f = font(size, bold)
        box = d.textbbox((0, 0), text, font=f)
        d.text(((W - (box[2] - box[0])) // 2, y), text, fill=color, font=f)
        y += lh
    img.save(path)


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def card_segment(png: Path, mp4: Path, secs: float) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-t",
            str(secs),
            "-i",
            str(png),
            "-vf",
            f"fade=t=in:d=0.4,fade=t=out:st={secs - 0.4}:d=0.4,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            str(mp4),
        ]
    )


def video_segment(src: Path, mp4: Path) -> None:
    """Normalize any input to the target frame at 30 fps with pillarboxing."""
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0e1014,fps=30,format=yuv420p"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-an",
            str(mp4),
        ]
    )


def main() -> None:
    out = Path("out")
    work = out / "showcase_parts"
    work.mkdir(parents=True, exist_ok=True)

    crowd = out / "morocco" / "annotated.mp4"
    fall = out / "fall01" / "annotated.mp4"
    for p in (crowd, fall):
        if not p.exists():
            sys.exit(f"missing input {p}; run the demo commands in DEMO.md first")

    card(
        work / "c1.png",
        [
            ("GUARDIANEYE", 92, FG, True),
            ("The AI safety officer for stadiums", 40, RED, False),
            ("", 20, FG, False),
            ("YOLO11 pose  ·  depth sensing  ·  real time on a laptop", 28, DIM, False),
        ],
    )
    card(
        work / "c2.png",
        [
            ("01  ·  CROWD MONITORING", 52, FG, True),
            ("", 16, FG, False),
            ("Real footage: packed international football stadium", 32, DIM, False),
            ("CSRNet crowd counting + live people/m2 density map + depth", 26, DIM, False),
        ],
    )
    card(
        work / "c3.png",
        [
            ("02  ·  COLLAPSE DETECTION", 52, FG, True),
            ("", 16, FG, False),
            ("Real Kinect depth sensor + YOLO pose (UR Fall dataset)", 32, DIM, False),
            ("Person down  ->  sustained-down confirmation  ->  zone alert", 26, DIM, False),
        ],
    )
    card(
        work / "c4.png",
        [
            ("Every stadium already owns the cameras.", 40, FG, True),
            ("GuardianEye is the software that watches back.", 40, FG, True),
            ("", 20, FG, False),
            ("~23 fps on a MacBook  ·  anonymous by design, no faces stored", 27, DIM, False),
            ("", 14, FG, False),
            ("github.com/PranavAchar01/guardianeye", 30, RED, False),
        ],
    )

    card_segment(work / "c1.png", work / "s0.mp4", 4.0)
    card_segment(work / "c2.png", work / "s1.mp4", 3.0)
    video_segment(crowd, work / "s2.mp4")
    card_segment(work / "c3.png", work / "s3.mp4", 3.0)
    video_segment(fall, work / "s4.mp4")
    card_segment(work / "c4.png", work / "s5.mp4", 5.0)

    concat = work / "list.txt"
    concat.write_text("".join(f"file 's{i}.mp4'\n" for i in range(6)))
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
            str(out / "showcase.mp4"),
        ]
    )
    print(f"showcase ready: {out / 'showcase.mp4'}")


if __name__ == "__main__":
    main()
