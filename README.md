# GuardianEye 🏟️

[![CI](https://github.com/PranavAchar01/guardianeye/actions/workflows/ci.yml/badge.svg)](https://github.com/PranavAchar01/guardianeye/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**The AI safety officer for stadiums.** Real-time collapse detection and
crowd-crush early warning from any elevated camera or drone feed — YOLO pose
estimation fused with a depth channel (hardware sensor or monocular model).

*Sports World Cup Hackathon 2026 — Track 4: Sports Business & Operations.*

🎬 **[Watch the showcase video](https://github.com/PranavAchar01/guardianeye/releases/tag/v0.1.0)** —
real Premier League stadium footage + collapse detection on a Kinect depth
recording (all processed videos attached to the v0.1.0 release).

## Why this should already exist

- A cardiac arrest in row 47 of an 80,000-seat stadium is invisible to medics
  until nearby fans start waving. **Survival drops ~10% per minute without
  CPR.** GuardianEye spots a person who goes down and stays down in seconds,
  and radioes a grid zone ("PERSON DOWN — ZONE B7").
- **Kanjuruhan Stadium 2022: 135 dead. Hillsborough 1989: 97.** Crowd crushes
  develop over minutes and are measurable: sustained density above ~5
  people/m² is the point of no return (Fruin; Still). GuardianEye converts
  every camera into a live people-per-m² risk map and fires an alert while
  there is still time to open gates.

One product, three failure modes of the same physics: too many bodies in one
place, one body on the ground — or one body about to go over an edge.

## Edge Watch: "will anyone fall off?"

From a drone or high camera, a drop edge (tier rail, beam end, roof opening)
is a sharp discontinuity in the depth map. Edge Watch traces those cliffs,
tracks every person's velocity with **ego-motion compensation** (optical-flow
median cancels the drone's own movement, so a stationary person never "drifts"
toward an edge), and fires a zone alert with a **time-to-edge** prediction
when someone's sustained trajectory crosses a drop — before the fall, not
after.

## How it works

```
video ──► YOLO11-pose (person boxes + 17 keypoints + ByteTrack IDs)
      ──► depth channel:
            • side-by-side sensor capture (Kinect/stereo)  --sensor-depth left
            • or Depth Anything V2 monocular estimation    (default)
      ──► self-calibrating scale: every detected person is a 1.7 m ruler;
          depth extends that scale to the whole frame (pinhole geometry)
      ──► density grid (people/m²) ─► Fruin/Still risk levels + stagnation
      ──► posture (torso angle) ─► down-time state machine ─► incidents
      ──► annotated video + HUD + zone alerts + metrics.json + report.html
```

No faces are identified or stored — detection is anonymous by design, which
is what makes it deployable at a real venue.

## Quickstart

```bash
uv sync
bash scripts/fetch_demo.sh

# Collapse detection on a real depth-sensor recording (UR Fall dataset,
# left pane = Kinect depth, right pane = RGB):
uv run guardianeye demo/fall-01.mp4 -o out/fall01 --sensor-depth left --confirm-secs 1.0

# Crowd density + tracking on an elevated pedestrian scene. Wide scenes with
# small/distant people need the detect weights (the nano *pose* model misses
# them; posture then falls back to box aspect, so collapse detection still
# works). Sparse crowd, so demo thresholds are lowered to exercise the alerts:
uv run guardianeye demo/pedestrians.avi -o out/peds --weights yolo11n.pt --thresholds 0.6,1.2,2.0

# Real stadium footage (wide night scene: detect weights, 1280px inference
# for distant fans, collapse detection scoped off — posture evidence is
# unreliable in dense seated crowds):
uv run guardianeye demo/stadium-cut.mp4 -o out/stadium \
  --weights yolo11n.pt --imgsz 1280 --conf 0.25 --thresholds 0.5,1.2,2.0 --no-fall

# Edge Watch on drone footage (people at height on a stadium structure):
uv run guardianeye demo/drone-cut.mp4 -o out/drone \
  --edge-watch --no-fall --weights yolo11n.pt --imgsz 1280 --conf 0.25 --depth-every 4

# Any drone/CCTV video, defaults (real-world thresholds 2 / 3.5 / 5 p/m²):
uv run guardianeye your_footage.mp4 -o out/run1

# Rebuild the demo montages from processed outputs:
uv run python scripts/make_showcase.py
uv run python scripts/make_edge_demo.py
```

Outputs per run: `annotated.mp4` (HUD, heatmap, boxes, incident markers,
depth inset), `report.html` (stats, sparklines, incident/crush tables),
`metrics.json` (full per-frame timeline).

## Key options

| Flag | Meaning |
|---|---|
| `--sensor-depth left\|right` | use a real depth pane from a side-by-side capture instead of the monocular model |
| `--no-depth` | skip depth entirely; scale comes from body heights only |
| `--thresholds T1,T2,T3` | density boundaries in people/m² (default 2, 3.5, 5 — literature values) |
| `--confirm-secs S` | continuous down-time before a medical incident confirms (default 2.0) |
| `--weights W` | any Ultralytics model; pose weights enable posture detection |
| `--imgsz N` | YOLO inference size; 1280 recovers small/distant people (default 640) |
| `--no-fall` | disable collapse detection for dense-crowd cameras (density still runs) |
| `--edge-watch` | drop-edge fall-off risk: depth-cliff hazard map + trajectory prediction |
| `--device auto\|mps\|cuda\|cpu` | inference device |

## Verification

```bash
uv run ruff check .          # lint
uv run pytest -q             # unit tests: density math, calibration,
                             # posture, incident state machine, hysteresis
```

## Honest limitations

- Density is an estimate: monocular depth is relative, the 1.7 m ruler is a
  population mean, and occlusion undercounts very dense crowds. Deployments
  should calibrate per-camera (one measured distance fixes absolute scale).
- Posture from a single camera degrades on straight-overhead drone shots
  (everyone's torso is horizontal in image space) — oblique/elevated views
  are the intended geometry, matching real stadium cameras.
- Demo footage is small-scale (research fall clips, sample pedestrian
  scenes); thresholds in the demo commands are lowered accordingly and the
  defaults are the real-world values.

## Data / licenses

Demo footage: [UR Fall Detection Dataset](https://fenix.ur.edu.pl/~mkepski/ds/uf.html)
(Kwolek & Kepski), OpenCV sample data, Intel `sample-videos`; Wikimedia
Commons: "Chelsea fans chanting at Tottenham stadium" (CC BY-SA 2.0) and
"Mercedes-Benz Stadium Drone Fly-Over" (CC BY 3.0). Models: Ultralytics
YOLO11 (AGPL-3.0), Depth Anything V2 (Apache-2.0).
