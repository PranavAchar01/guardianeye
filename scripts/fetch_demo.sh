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

# Real stadium footage (Wikimedia Commons; see README for licenses)
fetch "https://commons.wikimedia.org/wiki/Special:FilePath/Chelsea%20fans%20chanting%20at%20Tottenham%20stadium.webm" demo/stadium-chelsea.webm
fetch "https://commons.wikimedia.org/wiki/Special:FilePath/Mercedes-Benz%20Stadium%20Drone%20Fly-Over.webm" demo/drone-mbs.webm

# Stadium density segment (85-112s of the Chelsea clip)
[ -f demo/stadium-cut.mp4 ] || ffmpeg -y -loglevel error -ss 85 -t 27 -i demo/stadium-chelsea.webm \
  -c:v libx264 -pix_fmt yuv420p -an demo/stadium-cut.mp4

# Drone edge-watch input: hone-in zoom + worker-at-height segments
if [ ! -f demo/drone-cut.mp4 ]; then
  T=$(mktemp -d)
  ffmpeg -y -loglevel error -ss 62 -t 4 -i demo/drone-mbs.webm \
    -vf "crop=w='iw/(1+min(t/4,1))':h='ih/(1+min(t/4,1))':x='(iw-ow)*0.55':y='(ih-oh)*0.5',scale=1280:720:flags=lanczos,fps=30" \
    -c:v libx264 -an "$T/a.mp4"
  ffmpeg -y -loglevel error -ss 66 -t 12 -i demo/drone-mbs.webm \
    -vf "scale=1280:720:flags=lanczos,fps=30" -c:v libx264 -an "$T/b.mp4"
  ffmpeg -y -loglevel error -ss 49 -t 12 -i demo/drone-mbs.webm \
    -vf "scale=1280:720:flags=lanczos,fps=30" -c:v libx264 -an "$T/c.mp4"
  printf "file '%s/a.mp4'\nfile '%s/b.mp4'\nfile '%s/c.mp4'\n" "$T" "$T" "$T" > "$T/list.txt"
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$T/list.txt" -c:v libx264 -pix_fmt yuv420p demo/drone-cut.mp4
  rm -rf "$T"
fi
echo "demo footage ready in demo/"
