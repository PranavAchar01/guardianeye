#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="out/promo_v2/voice"
mkdir -p "$OUT"

say -v Daniel -r 168 -o "$OUT/vo-00.aiff" \
  "At a stadium, eighty thousand voices can hide one silent emergency."

say -v Daniel -r 168 -o "$OUT/vo-01.aiff" \
  "A camera can see the crowd. GuardianEye finds the signal."

say -v Daniel -r 168 -o "$OUT/vo-02.aiff" \
  "Meet GuardianEye: the AI safety officer for stadiums, turning existing elevated cameras and drone footage into one venue safety layer."

say -v Daniel -r 168 -o "$OUT/vo-03.aiff" \
  "It combines persistent person tracking, pose, and sensor or monocular depth to build a live people-per-square-metre risk map. As pressure builds, or a dense crowd stops moving, operators can see the hotspot early enough to act."

say -v Daniel -r 168 -o "$OUT/vo-04.aiff" \
  "Edge Watch traces dangerous drop boundaries, cancels the drone's own movement, and follows each trajectory toward the edge: warning before a fall, not after."

say -v Daniel -r 168 -o "$OUT/vo-05.aiff" \
  "When someone goes down, GuardianEye checks posture and sustained down-time. Once confirmed, it delivers a radio-ready location: medical emergency, Zone E four."

say -v Daniel -r 168 -o "$OUT/vo-06.aiff" \
  "Crowd crush. Medical collapse. Fall prevention. Three risks, one system, designed to run at the venue edge, with no face recognition and no identity profiles."

say -v Daniel -r 168 -o "$OUT/vo-07.aiff" \
  "The cameras are already watching. GuardianEye makes them understand. See sooner. Act sooner."

echo "narration ready in $OUT"
