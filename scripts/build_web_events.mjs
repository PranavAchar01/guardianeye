/**
 * Distill GuardianEye run metrics into a compact JSON the web app ships and
 * feeds to the Lyzr safety-officer agent. Run from repo root:
 *   node scripts/build_web_events.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";

const load = (p) => JSON.parse(readFileSync(p, "utf8"));

function downsample(frames, key, n = 40) {
  if (frames.length <= n) return frames.map((f) => +(f[key] ?? 0));
  const step = frames.length / n;
  return Array.from({ length: n }, (_, i) => +(frames[Math.floor(i * step)][key] ?? 0).toFixed(2));
}

function scene(id, file, meta) {
  const m = load(file);
  const frames = m.frames ?? [];
  const counts = frames.map((f) => f.count ?? 0);
  return {
    id,
    ...meta,
    n_frames: m.n_frames,
    fps: Math.round(m.fps),
    depth_source: m.depth_source,
    peak_count: m.peak_count,
    peak_density: +(+m.peak_density).toFixed(2),
    mean_count: Math.round(counts.reduce((a, b) => a + b, 0) / Math.max(counts.length, 1)),
    worst_level: ["SAFE", "MODERATE", "HIGH", "CRITICAL"][m.worst_level ?? 0],
    crush_episodes: m.alerts ?? [],
    incidents: m.incidents ?? [],
    edge_events: m.edge_events ?? [],
    density_series: downsample(frames, "max_density"),
    count_series: downsample(frames, "count"),
  };
}

const events = {
  generated_note: "Distilled from real GuardianEye runs; see github.com/PranavAchar01/guardianeye",
  scenes: [
    scene("crowd", "out/morocco/metrics.json", {
      title: "Crowd Monitoring",
      venue: "Packed international football stadium",
      model: "YOLO11x sliced tiles + CSRNet + Depth Anything V2 Large",
    }),
    scene("collapse", "out/fall01/metrics.json", {
      title: "Collapse Detection",
      venue: "Depth-sensor recording (Kinect RGB+D)",
      model: "YOLO11 pose + hardware depth",
    }),
    scene("edge", "out/drone/metrics.json", {
      title: "Edge Watch",
      venue: "Drone above stadium structure",
      model: "YOLO11x + depth-cliff hazard map + trajectory prediction",
    }),
  ],
};

writeFileSync("web/lib/events.json", JSON.stringify(events, null, 2));
const tot = events.scenes.reduce(
  (a, s) => a + s.incidents.length + s.edge_events.length + s.crush_episodes.length,
  0
);
console.log(
  `wrote web/lib/events.json: ${events.scenes.length} scenes, ${tot} safety events, ` +
    `peak crowd ${Math.max(...events.scenes.map((s) => s.peak_count))}`
);
