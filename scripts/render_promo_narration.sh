#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="out/promo_v2/voice"
mkdir -p "$OUT"
VOICE="Reed (English (UK))"

say -v "$VOICE" -r 158 -o "$OUT/vo-00.aiff" \
  "In a stadium, eighty thousand voices can make one silent emergency... disappear."

say -v "$VOICE" -r 166 -o "$OUT/vo-01.aiff" \
  "The cameras see the crowd. Guardian Eye sees what matters."

say -v "$VOICE" -r 174 -o "$OUT/vo-02.aiff" \
  "Meet Guardian Eye, the AI safety officer for stadiums. It turns existing cameras and drones into one live safety layer."

say -v "$VOICE" -r 174 -o "$OUT/vo-03.aiff" \
  "It tracks movement, posture, and depth, anonymously, then builds a live map of crowd pressure. When a pocket gets too dense... or suddenly stops moving... the control room sees it early enough to act."

say -v "$VOICE" -r 158 -o "$OUT/vo-04.aiff" \
  "Near a drop, Edge Watch draws the danger line, stabilizes the drone's motion, and follows every path toward it, so teams get a warning before a fall. Not after."

say -v "$VOICE" -r 174 -o "$OUT/vo-05.aiff" \
  "And if someone goes down? Guardian Eye checks their posture... and whether they stay down. Once it's sure, responders get what they need: medical emergency... Zone E four."

say -v "$VOICE" -r 162 -o "$OUT/vo-06.aiff" \
  "Crowd crush. Medical collapse. Falls. Three critical risks, one system, running at the venue edge. No face recognition. No identity profiles."

say -v "$VOICE" -r 152 -o "$OUT/vo-07.aiff" \
  "Your cameras already watch the crowd. Guardian Eye helps them understand it. See sooner. Act sooner."

echo "narration ready in $OUT"
