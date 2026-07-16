#!/usr/bin/env bash
# Fetch demo footage (openly licensed research/sample videos).
#  - UR Fall Detection Dataset (Univ. of Rzeszow): side-by-side Kinect DEPTH+RGB
#  - OpenCV sample data: elevated pedestrian scene
#  - Intel IoT sample-videos: people detection scene
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p demo

fetch() { [ -f "$2" ] || curl -sL --fail --max-time 90 -o "$2" "$1" && echo "ok  $2"; }

fetch "https://fenix.ur.edu.pl/~mkepski/ds/data/fall-01-cam0.mp4" demo/fall-01.mp4
fetch "https://fenix.ur.edu.pl/~mkepski/ds/data/fall-05-cam0.mp4" demo/fall-05.mp4
fetch "https://fenix.ur.edu.pl/~mkepski/ds/data/fall-12-cam0.mp4" demo/fall-12.mp4
fetch "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/vtest.avi" demo/pedestrians.avi
fetch "https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4" demo/people-detection.mp4
echo "demo footage ready in demo/"
