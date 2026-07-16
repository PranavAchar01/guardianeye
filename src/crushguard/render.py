"""Frame annotation: density heatmap, person boxes, risk zones, HUD, depth inset."""

from __future__ import annotations

import math

import cv2
import numpy as np

from .density import DensityGrid
from .detection import Person
from .risk import LEVEL_COLORS_BGR, LEVELS, Zone

HUD_H = 40
_HEAT_STOPS = [  # (position, BGR) — transparent-green through red
    (0.00, (60, 120, 40)),
    (0.30, (60, 190, 70)),
    (0.55, (0, 215, 255)),
    (0.78, (0, 140, 255)),
    (1.00, (50, 50, 235)),
]


def _build_heat_lut() -> np.ndarray:
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        for (p0, c0), (p1, c1) in zip(_HEAT_STOPS[:-1], _HEAT_STOPS[1:], strict=True):
            if p0 <= t <= p1:
                f = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
                lut[i] = [round(c0[k] + f * (c1[k] - c0[k])) for k in range(3)]
                break
    return lut


_HEAT_LUT = _build_heat_lut()


def heatmap_overlay(frame: np.ndarray, grid: DensityGrid, critical: float) -> np.ndarray:
    """Alpha-blend a density heatmap onto the frame (hotter = denser)."""
    h, w = frame.shape[:2]
    norm = np.clip(grid.density / max(critical, 1e-6), 0.0, 1.0)
    norm_full = cv2.resize(norm.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    norm_full = np.clip(norm_full, 0.0, 1.0)
    color = _HEAT_LUT[(norm_full * 255).astype(np.uint8)]
    alpha = np.where(norm_full > 0.06, 0.15 + 0.45 * norm_full, 0.0)[..., None]
    return (frame * (1 - alpha) + color * alpha).astype(np.uint8)


def draw_persons(
    frame: np.ndarray, persons: list[Person], levels: np.ndarray, grid: DensityGrid
) -> None:
    for p in persons:
        x1, y1, x2, y2 = (int(v) for v in p.box)
        r, c = grid.cell_of(*p.foot)
        color = LEVEL_COLORS_BGR[int(levels[r, c])]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
        if p.track_id is not None:
            cv2.putText(
                frame,
                str(p.track_id),
                (x1, max(y1 - 3, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                color,
                1,
                cv2.LINE_AA,
            )


def draw_zones(frame: np.ndarray, zones: list[Zone], levels: np.ndarray, cell_px: int) -> None:
    for z in zones:
        color = LEVEL_COLORS_BGR[z.level]
        for r, c in z.cells:
            x0, y0 = c * cell_px, r * cell_px
            cv2.rectangle(frame, (x0, y0), (x0 + cell_px, y0 + cell_px), color, 2)
        cx, cy = (int(v) for v in z.centroid_px)
        label = f"Z{z.zone_id} {z.peak_density:.1f}p/m2"
        cv2.putText(
            frame,
            label,
            (cx - 40, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame, label, (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
        )


def draw_hud(
    frame: np.ndarray,
    count: int,
    peak_density: float,
    frame_level: int,
    t: float,
    alert_on: bool,
    frame_idx: int,
) -> np.ndarray:
    """Top status bar plus a pulsing banner while a crush alert is active."""
    h, w = frame.shape[:2]
    out = frame.copy()
    cv2.rectangle(out, (0, 0), (w, HUD_H), (25, 22, 20), -1)
    frame = cv2.addWeighted(out, 0.82, frame, 0.18, 0)

    color = LEVEL_COLORS_BGR[frame_level]
    txt = f"CRUSHGUARD  |  t={t:6.1f}s  |  PEOPLE: {count:3d}  |  PEAK: {peak_density:4.1f} p/m2"
    cv2.putText(
        frame, txt, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA
    )
    status = LEVELS[frame_level]
    (tw, _), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (w - tw - 26, 7), (w - 8, HUD_H - 7), color, -1)
    cv2.putText(
        frame,
        status,
        (w - tw - 17, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (15, 15, 15),
        2,
        cv2.LINE_AA,
    )

    if alert_on:
        pulse = 0.55 + 0.35 * math.sin(frame_idx * 0.35)
        banner = frame.copy()
        y0 = HUD_H + 6
        cv2.rectangle(banner, (0, y0), (w, y0 + 34), (40, 40, 220), -1)
        frame = cv2.addWeighted(banner, pulse, frame, 1 - pulse, 0)
        msg = "!! CRUSH RISK - DISPERSE ZONE NOW !!"
        (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.putText(
            frame,
            msg,
            ((w - tw) // 2, y0 + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return frame


def draw_depth_inset(frame: np.ndarray, distance: np.ndarray | None, scale: float = 0.24) -> None:
    """Picture-in-picture view of the depth channel, bottom-right."""
    if distance is None:
        return
    h, w = frame.shape[:2]
    iw, ih = int(w * scale), int(h * scale)
    lo, hi = float(distance.min()), float(distance.max())
    norm = (distance - lo) / (hi - lo) if hi > lo else np.zeros_like(distance)
    vis = cv2.applyColorMap(((1 - norm) * 255).astype(np.uint8), cv2.COLORMAP_MAGMA)
    vis = cv2.resize(vis, (iw, ih), interpolation=cv2.INTER_AREA)
    x0, y0 = w - iw - 8, h - ih - 8
    frame[y0 : y0 + ih, x0 : x0 + iw] = vis
    cv2.rectangle(frame, (x0, y0), (x0 + iw, y0 + ih), (200, 200, 200), 1)
    cv2.putText(
        frame,
        "DEPTH",
        (x0 + 6, y0 + 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def draw_legend(frame: np.ndarray, thresholds: tuple[float, float, float]) -> None:
    labels = [
        f"<{thresholds[0]:g}",
        f"{thresholds[0]:g}-{thresholds[1]:g}",
        f"{thresholds[1]:g}-{thresholds[2]:g}",
        f">{thresholds[2]:g} p/m2",
    ]
    x, y = 8, frame.shape[0] - 12
    for lvl in range(4):
        cv2.rectangle(frame, (x, y - 10), (x + 14, y + 2), LEVEL_COLORS_BGR[lvl], -1)
        cv2.putText(
            frame,
            labels[lvl],
            (x + 18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        x += 18 + 8 * len(labels[lvl]) + 12


def render_frame(
    frame: np.ndarray,
    persons: list[Person],
    grid: DensityGrid,
    levels: np.ndarray,
    zones: list[Zone],
    distance: np.ndarray | None,
    thresholds: tuple[float, float, float],
    t: float,
    frame_idx: int,
    alert_on: bool,
) -> np.ndarray:
    out = heatmap_overlay(frame, grid, critical=thresholds[2])
    draw_persons(out, persons, levels, grid)
    draw_zones(out, zones, levels, grid.cell_px)
    draw_depth_inset(out, distance)
    draw_legend(out, thresholds)
    return draw_hud(
        out,
        count=len(persons),
        peak_density=grid.max_density,
        frame_level=int(levels.max()) if levels.size else 0,
        t=t,
        alert_on=alert_on,
        frame_idx=frame_idx,
    )
