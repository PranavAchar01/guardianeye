"""Build two polished GuardianEye promo videos from the release demo footage.

Outputs:
  out/promo_v2/guardianeye-showcase-v2.mp4  (60 seconds)
  out/promo_v2/guardianeye-film-90s.mp4      (90 seconds)

The edit intentionally uses original motion graphics and procedural audio.
It borrows the energy of an international football broadcast without using
FIFA marks, protected patterns, typefaces, or music.

Usage:
  python3 scripts/make_promo_v2.py --prepare
  bash scripts/render_promo_narration.sh
  python3 scripts/make_promo_v2.py --finalize
"""

from __future__ import annotations

import argparse
import math
import random
import subprocess
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "video_assets"
RELEASE = ASSETS / "release"
GENERATED = ASSETS / "generated"
OUT = ROOT / "out" / "promo_v2"
WORK = OUT / "work"
FRAMES = WORK / "hero_frames"
VO_DIR = OUT / "voice"

W, H = 1280, 720
FPS = 30
BG = "#05070D"
WHITE = "#F5F7FA"
MUTED = "#A7AFBD"
RED = "#FF3B4D"
CYAN = "#27E0D0"
LIME = "#A6FF4D"
AMBER = "#FFC857"
VIOLET = "#7657FF"

FONT_DISPLAY = Path("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf")
FONT_BODY = Path("/System/Library/Fonts/Avenir Next Condensed.ttc")
FONT_MONO = Path("/System/Library/Fonts/SFNSMono.ttf")


def run(cmd: list[str], *, quiet: bool = False) -> None:
    if not quiet:
        print("  " + " ".join(str(x) for x in cmd))
    result = subprocess.run(cmd, text=True, capture_output=quiet)
    if result.returncode:
        detail = result.stderr[-4000:] if result.stderr else ""
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")


def probe_duration(path: Path) -> float:
    value = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        text=True,
    ).strip()
    return float(value)


def ensure_video_duration(path: Path, target: float) -> None:
    actual = probe_duration(path)
    if abs(actual - target) <= 0.02:
        return
    padded = path.with_name(path.stem + ".padded.mp4")
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={target:.6f},"
            f"trim=duration={target:.6f},setpts=PTS-STARTPTS,fps={FPS},"
            "settb=AVTB,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", "yuv420p", str(padded),
        ],
        quiet=True,
    )
    padded.replace(path)


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing required asset: {path}")


def font(path: Path, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size, index=index)


DISPLAY_132 = font(FONT_DISPLAY, 132)
DISPLAY_94 = font(FONT_DISPLAY, 94)
DISPLAY_64 = font(FONT_DISPLAY, 64)
DISPLAY_42 = font(FONT_DISPLAY, 42)
BODY_32 = font(FONT_BODY, 32)
BODY_26 = font(FONT_BODY, 26)
MONO_20 = font(FONT_MONO, 20)
MONO_16 = font(FONT_MONO, 16)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def smooth(v: float) -> float:
    v = clamp(v)
    return v * v * (3.0 - 2.0 * v)


def phase(t: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if t >= end else 0.0
    return smooth((t - start) / (end - start))


def rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    rgb = ImageColor_getrgb(color)
    return rgb[0], rgb[1], rgb[2], alpha


def ImageColor_getrgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def cover(
    image: Image.Image,
    zoom: float = 1.0,
    center: tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    src = image.convert("RGB")
    scale = max(W / src.width, H / src.height) * zoom
    rw, rh = int(src.width * scale), int(src.height * scale)
    resized = src.resize((rw, rh), Image.Resampling.LANCZOS)
    max_x = max(0, rw - W)
    max_y = max(0, rh - H)
    left = int(clamp(center[0]) * max_x)
    top = int(clamp(center[1]) * max_y)
    return resized.crop((left, top, left + W, top + H)).convert("RGBA")


def darken(image: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Brightness(image.convert("RGB")).enhance(factor).convert("RGBA")


def alpha_layer(size: tuple[int, int] = (W, H)) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def draw_centered(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    face: ImageFont.FreeTypeFont,
    fill: str | tuple[int, int, int, int],
    *,
    anchor: str = "mm",
    stroke_width: int = 0,
    stroke_fill: str = "#000000",
) -> None:
    draw.text(
        xy,
        text,
        font=face,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def draw_eye(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: float,
    *,
    alpha: int = 255,
    accent: str = RED,
) -> None:
    cx, cy = center
    rx = int(radius * 1.65)
    ry = int(radius * 0.92)
    color = rgba(accent, alpha)
    width = max(2, int(radius * 0.08))
    draw.arc((cx - rx, cy - ry, cx + rx, cy + ry), 200, 340, fill=color, width=width)
    draw.arc((cx - rx, cy - ry, cx + rx, cy + ry), 20, 160, fill=color, width=width)
    draw.ellipse(
        (cx - int(radius * 0.35), cy - int(radius * 0.35),
         cx + int(radius * 0.35), cy + int(radius * 0.35)),
        outline=rgba(WHITE, alpha),
        width=max(2, int(radius * 0.07)),
    )
    draw.ellipse(
        (cx - int(radius * 0.10), cy - int(radius * 0.10),
         cx + int(radius * 0.10), cy + int(radius * 0.10)),
        fill=color,
    )


def draw_wordmark(
    frame: Image.Image,
    t: float,
    *,
    start: float,
    y: int,
    scale: float = 1.0,
    subtitle: bool = True,
) -> None:
    reveal = phase(t, start, start + 0.75)
    if reveal <= 0:
        return
    layer = alpha_layer()
    d = ImageDraw.Draw(layer)
    face = font(FONT_DISPLAY, int(132 * scale))
    text = "GUARDIANEYE"
    bbox = d.textbbox((0, 0), text, font=face)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    d.text((x, y), text, font=face, fill=rgba(WHITE, int(255 * reveal)))
    clip_right = int(x + tw * reveal)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle((0, 0, clip_right, H), fill=255)
    layer.putalpha(ImageChops_multiply(layer.getchannel("A"), mask))
    frame.alpha_composite(layer)

    bar_p = phase(t, start + 0.30, start + 1.05)
    overlay = alpha_layer()
    od = ImageDraw.Draw(overlay)
    bar_w = int(420 * scale * bar_p)
    od.rounded_rectangle(
        (W // 2 - bar_w // 2, y + int(135 * scale), W // 2 + bar_w // 2,
         y + int(141 * scale)),
        radius=3,
        fill=rgba(RED, int(235 * bar_p)),
    )
    if subtitle:
        sub_p = phase(t, start + 0.80, start + 1.35)
        draw_centered(
            od,
            (W // 2, y + int(184 * scale)),
            "THE AI SAFETY OFFICER FOR STADIUMS",
            font(FONT_BODY, int(28 * scale)),
            rgba(WHITE, int(220 * sub_p)),
        )
    frame.alpha_composite(overlay)


def ImageChops_multiply(a: Image.Image, b: Image.Image) -> Image.Image:
    # Import lazily to keep the top-level dependency list compact.
    from PIL import ImageChops

    return ImageChops.multiply(a, b)


def write_pillow_video(
    out: Path,
    duration: float,
    render,
) -> None:
    if out.exists() and out.stat().st_size > 50_000:
        print(f"reusing {out.name}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(duration * FPS))
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{W}x{H}",
        "-framerate",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out),
    ]
    print(f"rendering {out.name} ({duration:.2f}s)")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(frames):
            t = i / FPS
            frame = render(t, duration).convert("RGB")
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg frame encoder failed for {out}")


def write_alpha_video(
    out: Path,
    duration: float,
    render,
) -> None:
    if out.exists() and out.stat().st_size > 50_000:
        print(f"reusing {out.name}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(duration * FPS))
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{W}x{H}",
        "-framerate",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "qtrle",
        "-pix_fmt",
        "argb",
        str(out),
    ]
    print(f"rendering {out.name} ({duration:.2f}s alpha FX)")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(frames):
            t = i / FPS
            frame = render(t, duration).convert("RGBA")
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg alpha encoder failed for {out}")


def render_transition_fx_factory(
    major_cues: list[float],
    minor_cues: list[float],
) -> callable:
    def render(t: float, duration: float) -> Image.Image:
        frame = alpha_layer()
        d = ImageDraw.Draw(frame)

        for idx, cue in enumerate(major_cues):
            dt = t - cue
            if not -0.55 <= dt <= 0.48:
                continue
            q = smooth((dt + 0.55) / 1.03)
            envelope = math.sin(math.pi * clamp((dt + 0.55) / 1.03))
            style = idx % 4

            if style == 0:
                # Velocity ribbons: three directional bands cross the frame.
                x = int(-780 + (W + 1560) * q)
                for band, color in enumerate((CYAN, RED, LIME)):
                    shift = band * 105
                    alpha = int((198 - 24 * band) * envelope)
                    d.polygon(
                        (
                            (x - 510 - shift, -70),
                            (x - 270 - shift, -70),
                            (x + 330 - shift, H + 70),
                            (x + 70 - shift, H + 70),
                        ),
                        fill=rgba(color, alpha),
                    )
                d.line(
                    (x - 180, 0, x + 410, H),
                    fill=rgba(WHITE, int(185 * envelope)),
                    width=5,
                )
            elif style == 1:
                # Arena aperture: a detected signal grows into the next scene.
                cx = int(W * (0.28 + 0.44 * q))
                cy = int(H * (0.60 - 0.22 * math.sin(math.pi * q)))
                radius = 22 + 780 * q
                for ring in range(4):
                    rr = radius - ring * 46
                    if rr > 3:
                        d.ellipse(
                            (cx - rr, cy - rr, cx + rr, cy + rr),
                            outline=rgba(RED if ring % 2 == 0 else CYAN,
                                         int((185 - ring * 30) * envelope)),
                            width=max(2, 10 - ring * 2),
                        )
                draw_eye(d, (cx, cy), 26 + 34 * envelope,
                         alpha=int(220 * envelope))
            elif style == 2:
                # Depth scanner: a luminous sensing plane sweeps through.
                x = int(-100 + (W + 200) * q)
                for off, color, width in (
                    (-48, VIOLET, 30), (-16, CYAN, 12), (0, WHITE, 4), (24, RED, 18)
                ):
                    d.rectangle(
                        (x + off - width, 0, x + off + width, H),
                        fill=rgba(color, int((120 if width > 5 else 210) * envelope)),
                    )
                for gy in range(36, H, 72):
                    d.line(
                        (0, gy, W, gy),
                        fill=rgba(CYAN, int(36 * envelope)),
                        width=1,
                    )
            else:
                # Tactical tiles snap in staggered rows, then clear.
                cols, rows = 7, 4
                tile_w, tile_h = W // cols + 2, H // rows + 2
                for row in range(rows):
                    for col in range(cols):
                        stagger = (row * 0.07 + col * 0.025) % 0.28
                        local = clamp((q - stagger) / 0.38)
                        tile_alpha = int(148 * math.sin(math.pi * local) * envelope)
                        if tile_alpha <= 0:
                            continue
                        color = (RED, CYAN, VIOLET, LIME)[(row + col) % 4]
                        x0, y0 = col * tile_w, row * tile_h
                        inset = int(12 * (1 - local))
                        d.rounded_rectangle(
                            (x0 + inset, y0 + inset, x0 + tile_w - inset,
                             y0 + tile_h - inset),
                            radius=10,
                            fill=rgba(color, tile_alpha),
                            outline=rgba(WHITE, int(75 * envelope)),
                            width=2,
                        )

            # A restrained two-frame impact flash binds visual and audio hits.
            flash = 1.0 - clamp(abs(dt) / 0.075)
            if flash > 0:
                d.rectangle((0, 0, W, H), fill=rgba(WHITE, int(42 * flash)))

        # Minor cuts get quick tracking scans, not another full-screen effect.
        for idx, cue in enumerate(minor_cues):
            dt = t - cue
            if not -0.22 <= dt <= 0.24:
                continue
            q = smooth((dt + 0.22) / 0.46)
            envelope = math.sin(math.pi * clamp((dt + 0.22) / 0.46))
            direction = -1 if idx % 2 else 1
            x = int((W + 160) * q) if direction > 0 else int(W + 80 - (W + 160) * q)
            color = (CYAN, RED, LIME)[idx % 3]
            d.rectangle((x - 4, 0, x + 4, H), fill=rgba(WHITE, int(160 * envelope)))
            d.rectangle((x - 22, 0, x + 22, H), fill=rgba(color, int(55 * envelope)))
            for y in (90, 235, 380, 525, 670):
                d.line(
                    (x - 56 * direction, y, x - 14 * direction, y),
                    fill=rgba(color, int(190 * envelope)),
                    width=3,
                )
        return frame

    return render


def bake_transition_fx(base: Path, overlay: Path, out: Path, duration: float) -> None:
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(base), "-i", str(overlay),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto,"
            "unsharp=5:5:0.22:5:5:0,format=yuv420p[outv]",
            "-map", "[outv]", "-an", "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
        ],
        quiet=True,
    )


def render_intro_factory() -> callable:
    source = Image.open(GENERATED / "stadium-intro.png").convert("RGB")

    def render(t: float, duration: float) -> Image.Image:
        p = t / duration
        zoom = 1.0 + 0.10 * smooth(p)
        cx = 0.50 - 0.12 * phase(t, 1.3, 4.4)
        cy = 0.50 + 0.04 * phase(t, 1.3, 4.4)
        frame = cover(source, zoom=zoom, center=(cx, cy))
        frame = darken(frame, 0.72 + 0.22 * phase(t, 0.0, 1.1))

        # Stadium floodlights wake in two waves.
        beams = alpha_layer()
        bd = ImageDraw.Draw(beams)
        left_p = phase(t, 0.25, 0.65)
        right_p = phase(t, 0.65, 1.05)
        if left_p:
            bd.polygon(
                ((120, 0), (360, 0), (600, H), (330, H)),
                fill=(235, 245, 255, int(32 * left_p * (1 - phase(t, 1.1, 1.8)))),
            )
        if right_p:
            bd.polygon(
                ((900, 0), (1160, 0), (980, H), (730, H)),
                fill=(235, 245, 255, int(28 * right_p * (1 - phase(t, 1.4, 2.0)))),
            )
        frame.alpha_composite(beams)

        # The crowd becomes a nervous system: many anonymous nodes, one signal.
        node_layer = alpha_layer()
        nd = ImageDraw.Draw(node_layer)
        nodes_p = phase(t, 1.1, 2.3) * (1.0 - phase(t, 4.5, 5.2))
        rng = random.Random(2601)
        for _ in range(120):
            x = rng.randint(160, 1120)
            y = rng.randint(275, 590)
            # Keep most points out of the pitch.
            if 405 < x < 930 and 410 < y < 640:
                continue
            r = 1 if rng.random() < 0.82 else 2
            nd.ellipse((x - r, y - r, x + r, y + r), fill=(240, 245, 250, int(120 * nodes_p)))
        target = (322, 427)
        signal_p = phase(t, 1.7, 2.2)
        nd.ellipse(
            (target[0] - 5, target[1] - 5, target[0] + 5, target[1] + 5),
            fill=rgba(RED, int(255 * signal_p)),
        )
        for k in range(4):
            local = (t - 1.8 - 0.52 * k) % 2.1
            if 0 <= local <= 1.35 and signal_p:
                rp = local / 1.35
                radius = 16 + 105 * rp
                alpha = int(210 * (1 - rp) * signal_p)
                nd.ellipse(
                    (target[0] - radius, target[1] - radius,
                     target[0] + radius, target[1] + radius),
                    outline=rgba(RED, alpha),
                    width=max(2, int(5 * (1 - rp))),
                )
        frame.alpha_composite(node_layer)

        # Three flowing broadcast bands sweep the signal into a single iris.
        ribbon_p = phase(t, 3.65, 4.30) * (1.0 - phase(t, 5.05, 5.55))
        if ribbon_p:
            ribbons = alpha_layer()
            rd = ImageDraw.Draw(ribbons)
            x0 = int(-520 + 1800 * ribbon_p)
            colors = (RED, CYAN, LIME)
            for idx, color in enumerate(colors):
                offset = idx * 74
                rd.polygon(
                    (
                        (x0 - 520 - offset, -40),
                        (x0 - 330 - offset, -40),
                        (x0 + 250 - offset, H + 40),
                        (x0 + 50 - offset, H + 40),
                    ),
                    fill=rgba(color, 182 - idx * 24),
                )
            frame.alpha_composite(ribbons.filter(ImageFilter.GaussianBlur(1.2)))

        iris_p = phase(t, 4.35, 5.20) * (1.0 - phase(t, 6.0, 6.7))
        if iris_p:
            eye_layer = alpha_layer()
            ed = ImageDraw.Draw(eye_layer)
            draw_eye(ed, (W // 2, 278), 42 + 34 * iris_p, alpha=int(240 * iris_p))
            frame.alpha_composite(eye_layer)

        draw_wordmark(frame, t, start=5.1, y=310, scale=0.82, subtitle=True)

        # Fade up from black, preserving a decisive cold open.
        if t < 0.75:
            black = Image.new("RGBA", (W, H), rgba(BG, 255))
            frame = Image.blend(black, frame, phase(t, 0.0, 0.75))
        return frame

    return render


def rounded_panel(image: Image.Image, size: tuple[int, int], radius: int = 26) -> Image.Image:
    fitted = ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    panel = fitted.convert("RGBA")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    panel.putalpha(mask)
    return panel


def extract_frame(src: Path, at: float, out: Path) -> None:
    if out.exists() and out.stat().st_size > 5_000:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{at:.3f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-vf",
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
            str(out),
        ],
        quiet=True,
    )


def render_synthesis_factory() -> callable:
    stadium = Image.open(FRAMES / "stadium.png").convert("RGB")
    edge = Image.open(FRAMES / "edge.png").convert("RGB")
    fall = Image.open(FRAMES / "fall.png").convert("RGB")
    sources = [stadium, fall, edge]
    accents = [CYAN, RED, LIME]

    def render(t: float, duration: float) -> Image.Image:
        frame = Image.new("RGBA", (W, H), rgba(BG, 255))
        p_in = phase(t, 0.0, 1.0)
        converge_start = duration * 0.48
        converge_end = duration * 0.74
        converge = phase(t, converge_start, converge_end)
        fade_panels = 1.0 - phase(t, duration * 0.70, duration * 0.80)

        layer = alpha_layer()
        ld = ImageDraw.Draw(layer)
        base_w, base_h = 360, 548
        centers = [226, 640, 1054]
        for idx, src in enumerate(sources):
            start_x = (-420 if idx == 0 else W + 420 if idx == 2 else W // 2)
            center_x = int(start_x + (centers[idx] - start_x) * p_in)
            center_y = 350
            target_x = W // 2 + (idx - 1) * 34
            target_y = 332 + (idx - 1) * 8
            center_x = int(center_x + (target_x - center_x) * converge)
            center_y = int(center_y + (target_y - center_y) * converge)
            pw = int(base_w * (1.0 - 0.72 * converge))
            ph = int(base_h * (1.0 - 0.72 * converge))
            panel = rounded_panel(
                src, (max(8, pw), max(8, ph)), radius=max(5, int(24 * (1 - converge)))
            )
            if fade_panels < 1:
                panel.putalpha(panel.getchannel("A").point(lambda a: int(a * fade_panels)))
            x, y = center_x - pw // 2, center_y - ph // 2
            layer.alpha_composite(panel, (x, y))
            ld.rounded_rectangle(
                (x - 4, y - 4, x + pw + 4, y + ph + 4),
                radius=max(7, int(26 * (1 - converge))),
                outline=rgba(accents[idx], int(220 * fade_panels)),
                width=max(2, int(5 * (1 - 0.55 * converge))),
            )

            # Wordless risk glyphs live on top of the real footage.
            if idx == 0 and converge < 0.65:
                glyphs = ((x + 80, y + 200, 26), (x + 145, y + 250, 34), (x + 240, y + 205, 29))
                for gx, gy, rr in glyphs:
                    ld.ellipse((gx - rr, gy - rr, gx + rr, gy + rr),
                               outline=rgba(AMBER, int(170 * fade_panels)), width=3)
            elif idx == 1 and converge < 0.65:
                rr = 54 + 8 * math.sin(t * math.tau * 1.5)
                ld.ellipse(
                    (center_x - rr, center_y + 105 - rr, center_x + rr, center_y + 105 + rr),
                    outline=rgba(RED, int(220 * fade_panels)),
                    width=5,
                )
            elif idx == 2 and converge < 0.65:
                ld.line((x + 55, y + 410, x + pw - 45, y + 305),
                        fill=rgba(LIME, int(220 * fade_panels)), width=5)
                ld.polygon(
                    ((x + pw - 45, y + 305), (x + pw - 75, y + 308), (x + pw - 58, y + 332)),
                    fill=rgba(LIME, int(220 * fade_panels)),
                )

        frame.alpha_composite(layer)

        # Three signals converge into one GuardianEye iris.
        signal_p = phase(t, converge_start + 0.4, duration * 0.80)
        if signal_p:
            signals = alpha_layer()
            sd = ImageDraw.Draw(signals)
            dest = (W // 2, 335)
            for idx, sx in enumerate(centers):
                points = []
                for n in range(41):
                    q = n / 40
                    x = sx + (dest[0] - sx) * q
                    y = 635 - 310 * q - 65 * math.sin(math.pi * q) * (idx - 1)
                    points.append((int(x), int(y)))
                visible = max(2, int(len(points) * signal_p))
                sd.line(points[:visible], fill=rgba(accents[idx], 210), width=5)
                dot = points[min(visible - 1, len(points) - 1)]
                sd.ellipse((dot[0] - 7, dot[1] - 7, dot[0] + 7, dot[1] + 7),
                           fill=rgba(accents[idx], 255))
            eye_p = phase(t, duration * 0.68, duration * 0.83)
            draw_eye(sd, dest, 55 + 28 * eye_p, alpha=int(245 * eye_p))
            frame.alpha_composite(signals)

        if t > duration * 0.76:
            fade = phase(t, duration * 0.76, duration * 0.88)
            shade = Image.new("RGBA", (W, H), (5, 7, 13, int(205 * fade)))
            frame.alpha_composite(shade)
            eye = alpha_layer()
            ed = ImageDraw.Draw(eye)
            draw_eye(ed, (W // 2, 270), 74, alpha=int(255 * fade))
            frame.alpha_composite(eye)
            draw_wordmark(
                frame,
                t,
                start=duration * 0.80,
                y=340,
                scale=0.72,
                subtitle=False,
            )
        return frame

    return render


def render_pipeline_factory() -> callable:
    stadium = Image.open(FRAMES / "stadium.png").convert("RGB")
    base = cover(stadium, zoom=1.03)
    gray = base.convert("RGB").convert("L")
    heat = ImageOps.colorize(gray, black="#250A4F", white="#FF6847").convert("RGBA")
    heat = Image.blend(base, heat, 0.68)
    detections = [
        (120, 205, 22, 40), (174, 244, 20, 36), (230, 195, 19, 34),
        (289, 264, 22, 40), (357, 215, 18, 34), (416, 272, 22, 42),
        (478, 225, 19, 36), (540, 280, 21, 39), (605, 220, 17, 33),
        (669, 271, 21, 40), (735, 215, 18, 34), (802, 265, 22, 40),
        (866, 207, 18, 34), (932, 253, 20, 38), (995, 198, 18, 34),
        (1057, 245, 20, 37), (1120, 205, 18, 34),
    ]

    def render(t: float, duration: float) -> Image.Image:
        frame = base.copy()
        frame.alpha_composite(Image.new("RGBA", (W, H), (3, 6, 12, 55)))
        scan_p = phase(t, 0.8, duration * 0.45)
        scan_x = int(W * scan_p)
        if scan_x > 0:
            frame.alpha_composite(heat.crop((0, 0, scan_x, H)), (0, 0))
        overlay = alpha_layer()
        od = ImageDraw.Draw(overlay)
        if 0 < scan_x < W:
            od.rectangle((scan_x - 3, 0, scan_x + 3, H), fill=rgba(CYAN, 235))
            od.rectangle((scan_x - 17, 0, scan_x + 17, H), fill=rgba(CYAN, 35))
        for x, y, bw, bh in detections:
            if x < scan_x:
                od.rectangle((x - bw // 2, y - bh, x + bw // 2, y),
                             outline=rgba(CYAN, 180), width=2)
                od.ellipse((x - 2, y - 2, x + 2, y + 2), fill=rgba(WHITE, 210))

        # Density cluster: circles compress and escalate in color.
        risk_p = phase(t, duration * 0.28, duration * 0.60)
        if risk_p:
            cluster = [(350, 470), (393, 495), (432, 459), (469, 506), (507, 470)]
            for idx, (x, y) in enumerate(cluster):
                r = 18 + 25 * risk_p + 5 * math.sin(t * 4 + idx)
                color = LIME if risk_p < 0.40 else AMBER if risk_p < 0.72 else RED
                od.ellipse((x - r, y - r, x + r, y + r),
                           outline=rgba(color, int(210 * risk_p)), width=4)

            # A person rotates from standing to prone.
            cx, cy = 680, 493
            angle = math.pi / 2 * risk_p
            length = 78
            dx, dy = math.sin(angle) * length, -math.cos(angle) * length
            od.line((cx, cy, cx + dx, cy + dy), fill=rgba(RED, int(240 * risk_p)), width=9)
            od.ellipse(
                (cx + dx - 11, cy + dy - 11, cx + dx + 11, cy + dy + 11),
                outline=rgba(WHITE, int(240 * risk_p)), width=4,
            )
            pulse = 32 + 9 * math.sin(t * math.tau * 1.4)
            od.ellipse((cx - pulse, cy - pulse, cx + pulse, cy + pulse),
                       outline=rgba(RED, int(180 * risk_p)), width=4)

            # Trajectory approaches a depth cliff but stops at the warning line.
            cliff_x = 986
            od.line((cliff_x, 418, cliff_x, 570), fill=rgba(RED, int(235 * risk_p)), width=6)
            od.line((cliff_x + 12, 420, cliff_x + 62, 450), fill=rgba(VIOLET, 170), width=3)
            od.line((cliff_x + 12, 560, cliff_x + 62, 530), fill=rgba(VIOLET, 170), width=3)
            dot_x = 824 + int(132 * min(0.88, risk_p))
            od.line((810, 520, dot_x, 500), fill=rgba(LIME, int(220 * risk_p)), width=5)
            od.polygon(((dot_x, 500), (dot_x - 18, 491), (dot_x - 14, 512)),
                       fill=rgba(LIME, int(220 * risk_p)))

        # Three alert paths route to one operator-ready iris.
        route_p = phase(t, duration * 0.58, duration * 0.88)
        if route_p:
            dest = (1110, 354)
            starts = ((480, 500, AMBER), (680, 500, RED), (950, 500, LIME))
            for sx, sy, color in starts:
                points = []
                for n in range(31):
                    q = n / 30
                    x = sx + (dest[0] - sx) * q
                    y = sy + (dest[1] - sy) * q - 70 * math.sin(math.pi * q)
                    points.append((int(x), int(y)))
                count = max(2, int(len(points) * route_p))
                od.line(points[:count], fill=rgba(color, 215), width=4)
            draw_eye(od, dest, 46 + 18 * route_p, alpha=int(240 * route_p))
        frame.alpha_composite(overlay)
        return frame

    return render


def render_deployment_factory() -> callable:
    control = Image.open(GENERATED / "control-room-outro.png").convert("RGB")

    def render(t: float, duration: float) -> Image.Image:
        frame = cover(control, zoom=1.0 + 0.055 * smooth(t / duration), center=(0.44, 0.53))
        frame = darken(frame, 0.62)
        overlay = alpha_layer()
        d = ImageDraw.Draw(overlay)
        alpha = int(235 * phase(t, 0.5, 1.4))

        # Existing camera -> local compute -> radio-ready zone, shown as icons.
        camera = (215, 360)
        chip = (640, 360)
        grid = (1060, 360)
        d.rounded_rectangle((camera[0] - 82, camera[1] - 54, camera[0] + 82, camera[1] + 54),
                            radius=16, outline=rgba(CYAN, alpha), width=5)
        d.polygon(((camera[0] + 82, camera[1] - 28),
                   (camera[0] + 124, camera[1] - 48),
                   (camera[0] + 124, camera[1] + 48),
                   (camera[0] + 82, camera[1] + 28)),
                  outline=rgba(CYAN, alpha), fill=rgba(BG, int(alpha * 0.55)))
        d.rounded_rectangle((chip[0] - 72, chip[1] - 72, chip[0] + 72, chip[1] + 72),
                            radius=14, outline=rgba(RED, alpha), width=6)
        for off in range(-54, 55, 36):
            d.line((chip[0] - 92, chip[1] + off, chip[0] - 72, chip[1] + off),
                   fill=rgba(RED, alpha), width=4)
            d.line((chip[0] + 72, chip[1] + off, chip[0] + 92, chip[1] + off),
                   fill=rgba(RED, alpha), width=4)
            d.line((chip[0] + off, chip[1] - 92, chip[0] + off, chip[1] - 72),
                   fill=rgba(RED, alpha), width=4)
            d.line((chip[0] + off, chip[1] + 72, chip[0] + off, chip[1] + 92),
                   fill=rgba(RED, alpha), width=4)
        draw_eye(d, chip, 40, alpha=alpha)
        d.rounded_rectangle((grid[0] - 95, grid[1] - 95, grid[0] + 95, grid[1] + 95),
                            radius=18, outline=rgba(LIME, alpha), width=5)
        for off in (-32, 32):
            d.line((grid[0] - 95, grid[1] + off, grid[0] + 95, grid[1] + off),
                   fill=rgba(LIME, int(alpha * 0.65)), width=3)
            d.line((grid[0] + off, grid[1] - 95, grid[0] + off, grid[1] + 95),
                   fill=rgba(LIME, int(alpha * 0.65)), width=3)
        zone_pulse = 13 + 8 * math.sin(t * math.tau * 1.5)
        d.ellipse((grid[0] - zone_pulse, grid[1] - zone_pulse,
                   grid[0] + zone_pulse, grid[1] + zone_pulse),
                  fill=rgba(RED, alpha))

        path_p = phase(t, 1.4, duration * 0.72)
        for idx, (x1, x2, color) in enumerate(((camera[0] + 130, chip[0] - 100, CYAN),
                                               (chip[0] + 100, grid[0] - 110, LIME))):
            d.line((x1, 360, x2, 360), fill=rgba(color, int(95 * path_p)), width=4)
            dot_x = int(x1 + (x2 - x1) * ((path_p * 1.35 - idx * 0.22) % 1.0))
            d.ellipse((dot_x - 7, 353, dot_x + 7, 367), fill=rgba(color, int(alpha * path_p)))
        frame.alpha_composite(overlay)
        return frame

    return render


def render_outro_factory() -> callable:
    control = Image.open(GENERATED / "control-room-outro.png").convert("RGB")

    def render(t: float, duration: float) -> Image.Image:
        p = t / duration
        frame = cover(control, zoom=1.0 + 0.07 * smooth(p), center=(0.46, 0.52))
        frame = darken(frame, 0.68)
        signal = alpha_layer()
        sd = ImageDraw.Draw(signal)
        converge = phase(t, 0.4, duration * 0.48)
        destinations = [(342, 242, CYAN), (640, 218, AMBER), (342, 500, RED), (650, 500, LIME)]
        center = (W // 2, 330)
        for idx, (sx, sy, color) in enumerate(destinations):
            pts = []
            for n in range(35):
                q = n / 34
                x = sx + (center[0] - sx) * q
                y = sy + (center[1] - sy) * q + (idx - 1.5) * 34 * math.sin(math.pi * q)
                pts.append((int(x), int(y)))
            count = max(2, int(len(pts) * converge))
            sd.line(pts[:count], fill=rgba(color, 205), width=4)
            dot = pts[count - 1]
            sd.ellipse((dot[0] - 6, dot[1] - 6, dot[0] + 6, dot[1] + 6), fill=rgba(color, 255))
        draw_eye(sd, center, 48 + 28 * converge, alpha=int(245 * converge))
        frame.alpha_composite(signal)

        dark_p = phase(t, duration * 0.42, duration * 0.66)
        if dark_p:
            frame.alpha_composite(Image.new("RGBA", (W, H), (5, 7, 13, int(230 * dark_p))))
        eye_layer = alpha_layer()
        ed = ImageDraw.Draw(eye_layer)
        eye_p = phase(t, duration * 0.48, duration * 0.66)
        draw_eye(ed, (W // 2, 245), 58 + 26 * eye_p, alpha=int(255 * eye_p))
        frame.alpha_composite(eye_layer)
        draw_wordmark(frame, t, start=duration * 0.58, y=300, scale=0.78, subtitle=False)

        copy_p = phase(t, duration * 0.72, duration * 0.84)
        copy_layer = alpha_layer()
        cd = ImageDraw.Draw(copy_layer)
        draw_centered(
            cd,
            (W // 2, 520),
            "SEE SOONER.  ACT SOONER.",
            DISPLAY_42,
            rgba(WHITE, int(245 * copy_p)),
        )
        draw_centered(
            cd,
            (W // 2, 575),
            "SPORTS WORLD CUP HACKATHON 2026  /  TRACK 4",
            MONO_16,
            rgba(MUTED, int(220 * copy_p)),
        )
        url_p = phase(t, duration * 0.82, duration * 0.93)
        draw_centered(
            cd,
            (W // 2, 635),
            "github.com/PranavAchar01/guardianeye",
            BODY_26,
            rgba(RED, int(245 * url_p)),
        )
        frame.alpha_composite(copy_layer)
        return frame

    return render


def normalize_cut(
    src: Path,
    start: float,
    input_duration: float,
    out: Path,
    *,
    speed: float = 1.0,
    target_duration: float | None = None,
    fall_layout: bool = False,
) -> float:
    out.parent.mkdir(parents=True, exist_ok=True)
    natural = input_duration / speed
    target = natural if target_duration is None else target_duration
    if out.exists() and out.stat().st_size > 20_000:
        ensure_video_duration(out, target)
        return target
    pad = max(0.0, target - natural)
    if fall_layout:
        graph = (
            "[0:v]split=2[bg0][fg0];"
            f"[bg0]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},gblur=sigma=28,eq=brightness=-0.27:saturation=0.75[bg];"
            "[fg0]scale=960:720:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"drawbox=x=156:y=0:w=968:h=720:color={RED}@0.85:t=4,"
            f"setpts=(PTS-STARTPTS)/{speed:.8f},fps={FPS},"
            f"tpad=stop_mode=clone:stop_duration={pad:.8f},"
            "settb=AVTB,format=yuv420p[v]"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start:.6f}", "-t", f"{input_duration:.6f}",
            "-i", str(src),
            "-filter_complex", graph,
            "-map", "[v]",
        ]
    else:
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setpts=(PTS-STARTPTS)/{speed:.8f},fps={FPS},"
            f"tpad=stop_mode=clone:stop_duration={pad:.8f},"
            "settb=AVTB,format=yuv420p"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start:.6f}", "-t", f"{input_duration:.6f}",
            "-i", str(src),
            "-vf", vf,
        ]
    cmd += [
        "-t", f"{target:.6f}", "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "17", "-pix_fmt", "yuv420p", str(out),
    ]
    run(cmd, quiet=True)
    ensure_video_duration(out, target)
    return target


def join_xfade(
    paths: list[Path],
    durations: list[float],
    transitions: list[str],
    transition_durations: list[float],
    out: Path,
) -> tuple[float, list[float]]:
    if len(paths) != len(durations):
        raise ValueError("paths and durations differ")
    if len(paths) - 1 != len(transitions) or len(transitions) != len(transition_durations):
        raise ValueError("transition lists must have one fewer item than paths")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", str(p)]
    filters: list[str] = []
    for i, duration in enumerate(durations):
        filters.append(
            f"[{i}:v]trim=duration={duration:.6f},setpts=PTS-STARTPTS,"
            f"fps={FPS},settb=AVTB,setsar=1,format=yuv420p[v{i}]"
        )
    current = "v0"
    current_duration = durations[0]
    cue_times: list[float] = []
    for i in range(1, len(paths)):
        td = transition_durations[i - 1]
        offset = current_duration - td
        cue_times.append(offset)
        label = f"x{i}"
        filters.append(
            f"[{current}][v{i}]xfade=transition={transitions[i - 1]}:"
            f"duration={td:.6f}:offset={offset:.6f}[{label}]"
        )
        current = label
        current_duration += durations[i] - td
    filters.append(f"[{current}]format=yuv420p[outv]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[outv]", "-an", "-t", f"{current_duration:.6f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ]
    run(cmd, quiet=True)
    return current_duration, cue_times


def concat_hard(paths: list[Path], durations: list[float], out: Path) -> float:
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for path in paths:
        cmd += ["-i", str(path)]
    filters: list[str] = []
    refs = []
    for i, duration in enumerate(durations):
        filters.append(
            f"[{i}:v]trim=duration={duration:.6f},setpts=PTS-STARTPTS,"
            f"fps={FPS},settb=AVTB,setsar=1,format=yuv420p[v{i}]"
        )
        refs.append(f"[v{i}]")
    filters.append(f"{''.join(refs)}concat=n={len(paths)}:v=1:a=0[outv]")
    total = sum(durations)
    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[outv]",
        "-an", "-t", f"{total:.6f}", "-c:v", "libx264", "-preset", "medium",
        "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ]
    run(cmd, quiet=True)
    return total


def build_clip_sequence(
    name: str,
    src: Path,
    specs: list[tuple[float, float, float]],
    *,
    transitions: list[str],
    transition_duration: float,
    fall_layout: bool = False,
) -> tuple[Path, float]:
    parts: list[Path] = []
    durations: list[float] = []
    part_dir = WORK / f"{name}_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    for i, (start, input_duration, output_duration) in enumerate(specs):
        speed = input_duration / output_duration
        path = part_dir / f"{i:02d}.mp4"
        durations.append(
            normalize_cut(
                src,
                start,
                input_duration,
                path,
                speed=speed,
                target_duration=output_duration,
                fall_layout=fall_layout,
            )
        )
        parts.append(path)
    out = WORK / f"{name}.mp4"
    tds = [transition_duration] * (len(parts) - 1)
    duration, _ = join_xfade(parts, durations, transitions, tds, out)
    return out, duration


def build_fall(name: str, target: float) -> tuple[Path, float]:
    src = RELEASE / "collapse-detection-demo.mp4"
    part_dir = WORK / f"{name}_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    if target < 8:
        specs = [
            (0.80, 1.80, 0.90),
            (2.60, 2.10, 2.10),
            (4.667, 0.666, 1.20),
            (5.20, 0.10, 2.00),
        ]
    else:
        specs = [
            (0.60, 2.50, 1.25),
            (3.10, 2.00, 2.00),
            (4.667, 0.666, 2.40),
            (5.20, 0.10, target - 5.65),
        ]
    paths: list[Path] = []
    durations: list[float] = []
    for i, (start, in_dur, out_dur) in enumerate(specs):
        path = part_dir / f"{i:02d}.mp4"
        durations.append(
            normalize_cut(
                src,
                start,
                in_dur,
                path,
                speed=in_dur / out_dur,
                target_duration=out_dur,
                fall_layout=True,
            )
        )
        paths.append(path)
    out = WORK / f"{name}.mp4"
    duration = concat_hard(paths, durations, out)
    return out, duration


def build_montage(name: str, target: float) -> tuple[Path, float]:
    stadium = RELEASE / "stadium-crowd-demo.mp4"
    edge = RELEASE / "edge-demo.mp4"
    fall = RELEASE / "collapse-detection-demo.mp4"
    choices = [
        (stadium, 24.00, False),
        (edge, 17.733, False),
        (fall, 3.50, True),
        (stadium, 8.50, False),
        (edge, 18.233, False),
        (fall, 4.667, True),
        (edge, 30.80, False),
        (stadium, 25.90, False),
        (edge, 13.90, False),
        (stadium, 20.30, False),
    ]
    count = len(choices)
    shot = target / count
    paths: list[Path] = []
    durations: list[float] = []
    part_dir = WORK / f"{name}_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    for i, (src, start, fall_layout) in enumerate(choices):
        path = part_dir / f"{i:02d}.mp4"
        durations.append(
            normalize_cut(
                src,
                start,
                shot,
                path,
                target_duration=shot,
                fall_layout=fall_layout,
            )
        )
        paths.append(path)
    out = WORK / f"{name}.mp4"
    duration = concat_hard(paths, durations, out)
    return out, duration


def prepare_visuals() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    FRAMES.mkdir(parents=True, exist_ok=True)
    VO_DIR.mkdir(parents=True, exist_ok=True)

    required = [
        RELEASE / "stadium-crowd-demo.mp4",
        RELEASE / "collapse-detection-demo.mp4",
        RELEASE / "edge-demo.mp4",
        GENERATED / "stadium-intro.png",
        GENERATED / "control-room-outro.png",
        ASSETS / "stadium-source.webm",
    ]
    for path in required:
        require(path)

    extract_frame(RELEASE / "stadium-crowd-demo.mp4", 24.10, FRAMES / "stadium.png")
    extract_frame(RELEASE / "edge-demo.mp4", 18.15, FRAMES / "edge.png")
    extract_frame(RELEASE / "collapse-detection-demo.mp4", 4.82, FRAMES / "fall.png")

    intro = WORK / "intro-8s.mp4"
    synthesis_show = WORK / "synthesis-9s.mp4"
    synthesis_film = WORK / "synthesis-11s.mp4"
    pipeline = WORK / "pipeline-8s.mp4"
    deployment = WORK / "deployment-8s.mp4"
    outro_show = WORK / "outro-7s.mp4"
    outro_film = WORK / "outro-8_3s.mp4"
    write_pillow_video(intro, 8.0, render_intro_factory())
    write_pillow_video(synthesis_show, 9.0, render_synthesis_factory())
    write_pillow_video(synthesis_film, 11.0, render_synthesis_factory())
    write_pillow_video(pipeline, 8.0, render_pipeline_factory())
    write_pillow_video(deployment, 8.0, render_deployment_factory())
    write_pillow_video(outro_show, 7.0, render_outro_factory())
    write_pillow_video(outro_film, 8.3, render_outro_factory())

    stadium_show, stadium_show_d = build_clip_sequence(
        "stadium-show",
        RELEASE / "stadium-crowd-demo.mp4",
        [
            (4.267, 3.900, 3.900),
            (8.867, 3.900, 3.900),
            (19.167, 3.900, 3.900),
            (22.767, 3.900, 3.900),
        ],
        transitions=["hrslice", "smoothleft", "diagtl"],
        transition_duration=0.2,
    )
    edge_show, edge_show_d = build_clip_sequence(
        "edge-show",
        RELEASE / "edge-demo.mp4",
        [
            (4.000, 2.500, 2.500),
            (13.500, 3.000, 3.000),
            (17.367, 2.633, 2.800),
            (20.200, 3.000, 3.000),
            (29.067, 2.500, 2.500),
        ],
        transitions=["hblur", "circleopen", "smoothleft", "diagtl"],
        transition_duration=0.2,
    )
    fall_show, fall_show_d = build_fall("fall-show", 6.2)
    montage_show, montage_show_d = build_montage("montage-show", 4.5)

    showcase_silent = OUT / "guardianeye-showcase-v2-silent.mp4"
    show_durations = [
        8.0,
        stadium_show_d,
        edge_show_d,
        fall_show_d,
        9.0,
        montage_show_d,
        7.0,
    ]
    # The transparent FX layer carries the visual identity; these underlying
    # blends stay smooth so no stock-looking slice/pixel preset shows through.
    show_transitions = [
        "smoothleft", "smoothright", "fadefast",
        "fadefast", "fadefast", "smoothleft",
    ]
    show_tds = [0.5, 0.5, 0.4, 0.5, 0.4, 0.4]
    show_duration, show_cues = join_xfade(
        [intro, stadium_show, edge_show, fall_show, synthesis_show, montage_show, outro_show],
        show_durations,
        show_transitions,
        show_tds,
        showcase_silent,
    )
    if abs(show_duration - 60.0) > 0.05:
        raise RuntimeError(f"showcase duration drifted to {show_duration:.3f}s")

    stadium_film, stadium_film_d = build_clip_sequence(
        "stadium-film",
        RELEASE / "stadium-crowd-demo.mp4",
        [
            (4.267, 4.500, 4.650),
            (8.767, 4.500, 4.650),
            (18.667, 4.500, 4.650),
            (22.167, 4.500, 4.650),
        ],
        transitions=["hrslice", "smoothleft", "diagtl"],
        transition_duration=0.2,
    )
    edge_film, edge_film_d = build_clip_sequence(
        "edge-film",
        RELEASE / "edge-demo.mp4",
        [
            (4.000, 3.800, 3.800),
            (12.700, 3.800, 3.800),
            (17.367, 2.633, 3.800),
            (20.000, 3.200, 3.800),
            (27.767, 3.800, 3.800),
        ],
        transitions=["diagtl", "circleopen", "hblur", "smoothleft"],
        transition_duration=0.2,
    )
    fall_film, fall_film_d = build_fall("fall-film", 10.0)
    montage_film, montage_film_d = build_montage("montage-film", 5.0)

    film_silent = OUT / "guardianeye-film-90s-silent.mp4"
    film_durations = [
        8.0,
        8.0,
        stadium_film_d,
        edge_film_d,
        fall_film_d,
        11.0,
        8.0,
        montage_film_d,
        8.3,
    ]
    film_transitions = [
        "smoothleft", "smoothright", "fadefast", "smoothleft",
        "fadefast", "smoothright", "fadefast", "smoothleft",
    ]
    film_tds = [0.6, 0.5, 0.5, 0.5, 0.6, 0.5, 0.5, 0.8]
    film_duration, film_cues = join_xfade(
        [
            intro,
            pipeline,
            stadium_film,
            edge_film,
            fall_film,
            synthesis_film,
            deployment,
            montage_film,
            outro_film,
        ],
        film_durations,
        film_transitions,
        film_tds,
        film_silent,
    )
    if abs(film_duration - 90.0) > 0.05:
        raise RuntimeError(f"film duration drifted to {film_duration:.3f}s")

    # Layer original sports-broadcast motion over both edits. Major cues sit on
    # section changes; minor cues add fast tracking scans at internal camera cuts.
    show_minor_cues = [
        11.20, 14.90, 18.60,
        24.30, 27.10, 29.70, 32.50,
        35.50, 37.60, 38.80, 56.40,
    ]
    film_minor_cues = [
        19.35, 23.80, 28.25,
        36.00, 39.60, 43.20, 46.80,
        51.35, 53.35, 55.75, 74.20, 85.30,
    ]
    show_impact_cues = [cue + td / 2 for cue, td in zip(show_cues, show_tds, strict=True)]
    film_impact_cues = [cue + td / 2 for cue, td in zip(film_cues, film_tds, strict=True)]
    show_fx = WORK / "showcase-transition-fx-v2.mov"
    film_fx = WORK / "film-transition-fx-v2.mov"
    write_alpha_video(
        show_fx,
        show_duration,
        render_transition_fx_factory(show_impact_cues, show_minor_cues),
    )
    write_alpha_video(
        film_fx,
        film_duration,
        render_transition_fx_factory(film_impact_cues, film_minor_cues),
    )
    showcase_immersive = OUT / "guardianeye-showcase-v2-immersive-silent.mp4"
    film_immersive = OUT / "guardianeye-film-90s-immersive-silent.mp4"
    bake_transition_fx(showcase_silent, show_fx, showcase_immersive, show_duration)
    bake_transition_fx(film_silent, film_fx, film_immersive, film_duration)

    extract_ambience()
    synth_soundtrack(
        WORK / "showcase-score-immersive.wav",
        show_duration,
        show_impact_cues,
        minor_cues=show_minor_cues,
        profile="showcase",
    )
    synth_soundtrack(
        WORK / "film-score-immersive.wav",
        film_duration,
        film_impact_cues,
        minor_cues=film_minor_cues,
        profile="film",
    )
    (WORK / "timing.txt").write_text(
        "\n".join(
            [
                f"showcase_duration={show_duration:.6f}",
                "showcase_cues=" + ",".join(f"{x:.3f}" for x in show_cues),
                "showcase_impact_cues=" + ",".join(f"{x:.3f}" for x in show_impact_cues),
                "showcase_minor_cues=" + ",".join(f"{x:.3f}" for x in show_minor_cues),
                f"film_duration={film_duration:.6f}",
                "film_cues=" + ",".join(f"{x:.3f}" for x in film_cues),
                "film_impact_cues=" + ",".join(f"{x:.3f}" for x in film_impact_cues),
                "film_minor_cues=" + ",".join(f"{x:.3f}" for x in film_minor_cues),
            ]
        )
        + "\n"
    )
    print(f"visual preparation complete: {OUT}")


def extract_ambience() -> None:
    out = WORK / "stadium-ambience.wav"
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", "85", "-t", "27",
            "-i", str(ASSETS / "stadium-source.webm"),
            "-vn", "-ac", "2", "-ar", "48000",
            "-af", "highpass=f=90,lowpass=f=10500,volume=0.72",
            str(out),
        ],
        quiet=True,
    )


def synth_soundtrack(
    out: Path,
    duration: float,
    cues: list[float],
    *,
    minor_cues: list[float] | None = None,
    profile: str,
) -> None:
    if out.exists() and abs(probe_duration(out) - duration) <= 0.02:
        print(f"reusing {out.name}")
        return
    print(f"synthesizing original {profile} score ({duration:.1f}s)")
    rate = 44_100
    total = int(round(duration * rate))
    rng = random.Random(2026 if profile == "showcase" else 2027)
    pcm = array("h")
    previous_noise = 0.0
    beat = 0.5  # 120 BPM
    roots = [55.0, 65.406, 48.999, 73.416]
    minor_cues = minor_cues or []
    cue_windows = [
        (c - 0.62, c, c + 0.55, idx, 1.0)
        for idx, c in enumerate(cues)
    ]
    cue_windows.extend(
        (c - 0.25, c, c + 0.24, idx + len(cues), 0.46)
        for idx, c in enumerate(minor_cues)
    )
    if profile == "showcase":
        alert_times = [34.3, 36.9, 38.0]
        energy_dip = (33.7, 40.5)
        radio_squelch_at = 38.05
    else:
        alert_times = [50.8, 53.4, 55.3]
        energy_dip = (49.6, 58.5)
        radio_squelch_at = 61.30

    for i in range(total):
        t = i / rate
        noise = rng.uniform(-1.0, 1.0)
        hp_noise = noise - previous_noise * 0.94
        previous_noise = noise

        intro = phase(t, 1.6, 5.5)
        ending = 1.0 - 0.45 * phase(t, duration - 7.0, duration - 1.0)
        if energy_dip[0] <= t <= energy_dip[1]:
            dip_mid = min(phase(t, energy_dip[0], energy_dip[0] + 1.0),
                          1.0 - phase(t, energy_dip[1] - 1.0, energy_dip[1]))
            energy = 1.0 - 0.55 * dip_mid
        else:
            energy = 1.0
        energy *= (0.18 + 0.82 * intro) * ending

        beat_local = t % beat
        beat_index = int(t / beat)
        kick_env = math.exp(-18.0 * beat_local)
        kick_phase = math.tau * (
            47.0 * beat_local + 3.2 * (1.0 - math.exp(-26.0 * beat_local))
        )
        kick = math.sin(kick_phase) * kick_env * 0.31 * energy

        bar = int(t / 2.0) % 4
        root = roots[bar]
        sidechain = 0.34 + 0.66 * min(1.0, beat_local / 0.14)
        bass = math.sin(math.tau * root * t) * 0.085 * energy * sidechain

        pad = (
            math.sin(math.tau * root * 2.0 * t)
            + 0.72 * math.sin(math.tau * root * 3.0 * t + 0.8)
            + 0.45 * math.sin(math.tau * root * 4.0 * t + 1.7)
        ) * 0.024 * (0.40 + 0.60 * intro)
        pad_right = (
            math.sin(math.tau * root * 2.0 * t + 0.11)
            + 0.72 * math.sin(math.tau * root * 3.0 * t + 0.91)
            + 0.45 * math.sin(math.tau * root * 4.0 * t + 1.52)
        ) * 0.024 * (0.40 + 0.60 * intro)

        eighth = t % 0.25
        arp_notes = [2.0, 2.5, 3.0, 4.0, 3.0, 2.5, 2.0, 1.5]
        arp_mul = arp_notes[int(t / 0.25) % len(arp_notes)]
        arp_env = math.exp(-7.5 * eighth)
        arp = (
            math.sin(math.tau * root * arp_mul * t)
            + 0.28 * math.sin(math.tau * root * arp_mul * 2.0 * t)
        ) * 0.026 * arp_env * energy
        arp_right = (
            math.sin(math.tau * root * arp_mul * t + 0.16)
            + 0.28 * math.sin(math.tau * root * arp_mul * 2.0 * t + 0.09)
        ) * 0.026 * arp_env * energy

        hat = hp_noise * math.exp(-75.0 * eighth) * 0.045 * energy
        snare = 0.0
        if beat_index % 4 in (1, 3):
            snare = hp_noise * math.exp(-22.0 * beat_local) * 0.085 * energy

        left_sfx = right_sfx = 0.0
        for start, center, end, idx, strength in cue_windows:
            if start <= t < center:
                q = (t - start) / (center - start)
                whoosh = hp_noise * (q**2.4) * 0.16 * strength
                if idx % 2:
                    left_sfx += whoosh * (1 - q * 0.7)
                    right_sfx += whoosh * (0.3 + q * 0.7)
                else:
                    left_sfx += whoosh * (0.3 + q * 0.7)
                    right_sfx += whoosh * (1 - q * 0.7)
            elif center <= t < end:
                q = t - center
                impact = math.sin(math.tau * (67.0 * q + 2.2 * (1 - math.exp(-20 * q))))
                impact *= math.exp(-10.5 * q) * 0.34 * strength
                ring = math.sin(math.tau * (1420.0 - 710.0 * q) * q)
                ring *= math.exp(-8.0 * q) * 0.052 * strength
                left_sfx += impact + ring
                right_sfx += impact + ring

        # Short data ticks punctuate internal camera changes.
        data_tick = 0.0
        for cue in minor_cues:
            dt = t - cue
            if 0 <= dt < 0.055:
                data_tick += math.sin(math.tau * 2050.0 * dt) * math.sin(
                    math.pi * dt / 0.055
                ) * 0.055
            elif 0.075 <= dt < 0.125:
                q = dt - 0.075
                data_tick += math.sin(math.tau * 1280.0 * q) * math.sin(
                    math.pi * q / 0.05
                ) * 0.042

        # A tactile radio-open texture makes the confirmed zone alert feel operational.
        radio = 0.0
        radio_dt = t - radio_squelch_at
        if -0.14 <= radio_dt < 0:
            q = (radio_dt + 0.14) / 0.14
            radio = hp_noise * (q**1.8) * 0.16
        elif 0 <= radio_dt < 0.12:
            radio = hp_noise * math.exp(-22.0 * radio_dt) * 0.15
            radio += math.sin(math.tau * 420.0 * radio_dt) * math.exp(
                -18.0 * radio_dt
            ) * 0.055

        alert = 0.0
        for at in alert_times:
            dt = t - at
            if 0 <= dt < 0.13:
                alert += math.sin(math.tau * 880.0 * dt) * math.sin(math.pi * dt / 0.13) * 0.11
            elif 0.18 <= dt < 0.31:
                q = dt - 0.18
                alert += math.sin(math.tau * 660.0 * q) * math.sin(math.pi * q / 0.13) * 0.10

        heartbeat = 0.0
        for hb in (1.05, 1.38, 2.38, 2.71):
            dt = t - hb
            if 0 <= dt < 0.28:
                heartbeat += math.sin(math.tau * 52.0 * dt) * math.exp(-17.0 * dt) * 0.30

        sonic = 0.0
        for note_t, freq in (
            (duration - 2.75, 293.665),
            (duration - 2.22, 369.994),
            (duration - 1.69, 440.000),
        ):
            dt = t - note_t
            if 0 <= dt < 1.15:
                sonic += (
                    math.sin(math.tau * freq * dt)
                    + 0.25 * math.sin(math.tau * freq * 2.0 * dt)
                ) * math.exp(-3.1 * dt) * 0.075

        shared = kick + bass + hat + snare + alert + heartbeat + sonic + data_tick + radio
        left = math.tanh((shared + pad + arp + left_sfx) * 1.10)
        right = math.tanh((shared + pad_right + arp_right + right_sfx) * 1.10)
        pcm.append(int(clamp(left, -1.0, 1.0) * 32767))
        pcm.append(int(clamp(right, -1.0, 1.0) * 32767))

    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


VOICE_STARTS = [0.45, 6.75, 11.40, 20.35, 35.40, 51.80, 64.50, 80.00]


def mix_showcase_audio() -> Path:
    score = WORK / "showcase-score-immersive.wav"
    ambience = WORK / "stadium-ambience.wav"
    out = WORK / "showcase-mix.m4a"
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(score), "-stream_loop", "-1", "-i", str(ambience),
            "-filter_complex",
            "[0:a]volume=0.90[score];"
            "[1:a]atrim=duration=60,asetpts=PTS-STARTPTS,"
            "stereowiden=delay=9:feedback=0.12:crossfeed=0.14:drymix=0.94,"
            "volume=0.085,"
            "volume=1.90:enable='between(t,7.5,22.25)',"
            "volume=0.42:enable='between(t,34.6,40.6)',"
            "volume=1.45:enable='between(t,48.9,53.2)',"
            "lowpass=f=3400:enable='between(t,34.6,40.6)',"
            "afade=t=in:st=0:d=2,afade=t=out:st=57:d=3[amb];"
            "[score][amb]amix=inputs=2:duration=first:normalize=0,"
            "loudnorm=I=-14:TP=-1:LRA=8,aresample=48000,"
            "alimiter=limit=0.68:attack=5:release=50:level=false:latency=true[outa]",
            "-map", "[outa]", "-t", "60", "-c:a", "aac", "-b:a", "256k", str(out),
        ],
        quiet=True,
    )
    return out


def mix_film_audio() -> Path:
    score = WORK / "film-score-immersive.wav"
    ambience = WORK / "stadium-ambience.wav"
    voice_files = [VO_DIR / f"vo-{i:02d}.aiff" for i in range(len(VOICE_STARTS))]
    missing = [p for p in voice_files if not p.exists() or p.stat().st_size < 10_000]
    if missing:
        raise SystemExit(
            "narration is missing; run `bash scripts/render_promo_narration.sh` first:\n"
            + "\n".join(str(p) for p in missing)
        )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(score), "-stream_loop", "-1", "-i", str(ambience),
    ]
    for voice in voice_files:
        cmd += ["-i", str(voice)]
    filters = [
        "[0:a]aresample=48000,volume=0.84[music]",
        "[1:a]atrim=duration=90,asetpts=PTS-STARTPTS,"
        "stereowiden=delay=9:feedback=0.12:crossfeed=0.14:drymix=0.94,"
        "volume=0.070,"
        "volume=2.10:enable='between(t,15.15,32.65)',"
        "volume=0.35:enable='between(t,50.1,59.8)',"
        "volume=1.60:enable='between(t,77.75,82.1)',"
        "lowpass=f=3400:enable='between(t,50.1,59.8)',"
        "afade=t=in:st=0:d=2,afade=t=out:st=87:d=3[amb]",
    ]
    voice_refs: list[str] = []
    for i, start in enumerate(VOICE_STARTS):
        stream = i + 2
        delay = int(round(start * 1000))
        label = f"vo{i}"
        filters.append(
            f"[{stream}:a]aresample=48000,highpass=f=65,lowpass=f=14000,"
            "deesser=i=0.18:m=0.35:f=0.55,"
            "acompressor=threshold=-18dB:ratio=2:attack=15:release=140,"
            f"volume=1.16,adelay={delay}|{delay}[{label}]"
        )
        voice_refs.append(f"[{label}]")
    filters.append(
        f"{''.join(voice_refs)}amix=inputs={len(voice_refs)}:"
        "duration=longest:normalize=0[voice]"
    )
    filters.append(
        "[voice]apad=whole_dur=90,atrim=duration=90,"
        "asplit=2[voice_sc][voice_mix]"
    )
    filters.append(
        "[music][amb]amix=inputs=2:duration=first:normalize=0[bed]"
    )
    filters.append(
        "[bed][voice_sc]sidechaincompress=threshold=0.04:ratio=4:knee=6:"
        "attack=12:release=300:detection=rms[ducked]"
    )
    filters.append(
        "[ducked][voice_mix]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-14:TP=-1:LRA=8,aresample=48000,"
        "alimiter=limit=0.68:attack=5:release=50:level=false:latency=true[outa]"
    )
    out = WORK / "film-mix.m4a"
    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[outa]",
        "-t", "90", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", str(out),
    ]
    run(cmd, quiet=True)
    return out


def mux(video: Path, audio: Path, out: Path, duration: float) -> None:
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "copy", "-t", f"{duration:.3f}", "-shortest",
            "-movflags", "+faststart", str(out),
        ],
        quiet=True,
    )


def finalize() -> None:
    showcase_silent = OUT / "guardianeye-showcase-v2-immersive-silent.mp4"
    film_silent = OUT / "guardianeye-film-90s-immersive-silent.mp4"
    for path in (
        showcase_silent,
        film_silent,
        WORK / "showcase-score-immersive.wav",
        WORK / "film-score-immersive.wav",
    ):
        require(path)
    show_audio = mix_showcase_audio()
    film_audio = mix_film_audio()
    mux(showcase_silent, show_audio, OUT / "guardianeye-showcase-v2.mp4", 60.0)
    mux(film_silent, film_audio, OUT / "guardianeye-film-90s.mp4", 90.0)
    print("final videos ready:")
    print(f"  {OUT / 'guardianeye-showcase-v2.mp4'}")
    print(f"  {OUT / 'guardianeye-film-90s.mp4'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare_visuals()
    else:
        finalize()


if __name__ == "__main__":
    main()
