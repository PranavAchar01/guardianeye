# GuardianEye: 3-minute demo script

## The hook (30s)

> "80,000 people in a stadium. One cardiac arrest in row 47. Survival drops
> 10% every minute without CPR, and today, medics find out when someone
> waves. Kanjuruhan Stadium, 2022: 135 people died in a crowd crush the
> cameras watched happen. GuardianEye is the AI safety officer that watches
> back."

## Live demo (90s)

1. **Collapse detection with a real depth sensor** (UR Fall dataset, Kinect
   depth pane + RGB pane):

   ```bash
   uv run guardianeye demo/fall-01.mp4 -o out/fall01 --sensor-depth left --confirm-secs 1.0
   open out/fall01/report.html
   ```

   Point at: person tracked → falls → red ring + down-timer → sustained-down
   confirmation → "MEDICAL EMERGENCY - ZONE E4" banner. The zone is what a
   steward radios. The depth inset is the sensor channel.

2. **Crowd density risk map** (elevated camera, monocular depth):

   ```bash
   uv run guardianeye demo/pedestrians.avi -o out/peds --weights yolo11n.pt --thresholds 0.6,1.2,2.0
   open out/peds/report.html
   ```

   Point at: per-person tracking IDs, live people/m² heatmap, depth inset
   estimated from a single lens, zero false medical alerts over 795 frames.

## Why it wins (60s)

- **Two failure modes, one physics, one product**: too many bodies in one
  place (crush), or one body on the ground (collapse).
- **Self-calibrating**: every detected person is a 1.7 m ruler; depth
  (sensor or monocular) spreads that scale across the frame. No site survey.
- **Runs at the edge**: ~23 fps on a MacBook, faster than the camera.
  No cloud, no latency, no footage leaving the venue.
- **Privacy is the feature**: no faces identified, no identities stored.
  That's what makes it deployable under GDPR/CCPA at a real venue.
- **Deployment path**: every stadium already owns the cameras. GuardianEye
  is software on the video wall.

## Numbers to quote

- Cardiac arrest survival: ~90% if defibrillated in minute 1; <10% by minute 10.
- Crush threshold: ≥5 people/m² loses individual control (Fruin, Still).
- Confirmed detection latency in demo: fall at t=3.4s, confirmed t=4.7s.
