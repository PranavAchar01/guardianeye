import eventsData from "./events.json";

export type CrushEpisode = { start_t: number; end_t: number; peak_density: number };
export type Incident = {
  track_id: number;
  start_t: number;
  confirmed_t: number | null;
  end_t: number | null;
  recovered?: boolean;
  zone: string;
  peak_down_s: number;
};
export type EdgeEvent = {
  track_id: number;
  start_t: number;
  zone: string;
  min_tte_s: number | null;
};
export type Scene = {
  id: string;
  title: string;
  venue: string;
  model: string;
  n_frames: number;
  fps: number;
  depth_source: string;
  peak_count: number;
  peak_density: number;
  mean_count: number;
  worst_level: string;
  crush_episodes: CrushEpisode[];
  incidents: Incident[];
  edge_events: EdgeEvent[];
  density_series: number[];
  count_series: number[];
};

export const events = eventsData as unknown as {
  generated_note: string;
  scenes: Scene[];
};

export function sceneById(id: string): Scene | undefined {
  return events.scenes.find((s) => s.id === id);
}

/** Compact, model-friendly telemetry string for a scene. */
export function telemetry(scene: Scene): string {
  const lines = [
    `SCENE: ${scene.title} — ${scene.venue}`,
    `Pipeline: ${scene.model}; depth source: ${scene.depth_source}`,
    `Duration: ${(scene.n_frames / scene.fps).toFixed(0)}s at ${scene.fps} fps`,
    `Crowd: peak ${scene.peak_count} people in frame, mean ${scene.mean_count}; peak density ${scene.peak_density} people/m^2 (worst level ${scene.worst_level})`,
  ];
  if (scene.crush_episodes.length) {
    lines.push(
      `Crush episodes (density >= critical): ${scene.crush_episodes
        .map((e) => `${e.start_t.toFixed(1)}-${e.end_t.toFixed(1)}s peak ${e.peak_density.toFixed(1)} p/m^2`)
        .join("; ")}`
    );
  } else {
    lines.push("Crush episodes: none");
  }
  if (scene.incidents.length) {
    lines.push(
      `Person-down incidents: ${scene.incidents
        .map(
          (i) =>
            `zone ${i.zone}, first down ${i.start_t.toFixed(1)}s, confirmed ${
              i.confirmed_t?.toFixed(1) ?? "n/a"
            }s, ${i.end_t == null ? "ONGOING at clip end" : i.recovered ? "recovered" : "track lost"}`
        )
        .join("; ")}`
    );
  } else {
    lines.push("Person-down incidents: none");
  }
  if (scene.edge_events.length) {
    lines.push(
      `Edge fall-risk events: ${scene.edge_events
        .map(
          (e) =>
            `zone ${e.zone} at ${e.start_t.toFixed(1)}s${
              e.min_tte_s != null ? `, ${e.min_tte_s.toFixed(1)}s to edge` : ""
            }`
        )
        .join("; ")}`
    );
  } else {
    lines.push("Edge fall-risk events: none");
  }
  return lines.join("\n");
}

export function allTelemetry(): string {
  return events.scenes.map(telemetry).join("\n\n");
}

/**
 * Deterministic safety briefing computed straight from the telemetry.
 * Used as the always-available fallback when Lyzr is not configured or
 * unreachable, so the app is never blank.
 */
export function fallbackBriefing(scene: Scene): string {
  const out: string[] = [];
  const urgent: string[] = [];

  for (const i of scene.incidents) {
    if (i.end_t == null) urgent.push(`MEDICAL: person down and unresolved in zone ${i.zone} — dispatch medics to ${i.zone} now.`);
    else if (!i.recovered) urgent.push(`MEDICAL: person-down in zone ${i.zone} lost from view before recovery — send a steward to verify ${i.zone}.`);
    else out.push(`Zone ${i.zone}: a fan went down (${i.peak_down_s.toFixed(0)}s) but was seen upright again — log and monitor.`);
  }
  for (const e of scene.edge_events) {
    urgent.push(
      `FALL RISK: movement toward a drop edge in zone ${e.zone}${
        e.min_tte_s != null ? ` (~${e.min_tte_s.toFixed(1)}s to edge)` : ""
      } — get a marshal to ${e.zone}.`
    );
  }
  for (const c of scene.crush_episodes) {
    urgent.push(
      `CRUSH: density hit ${c.peak_density.toFixed(1)} people/m^2 (${c.start_t.toFixed(0)}-${c.end_t.toFixed(0)}s) — relieve pressure / open gates for the affected zone.`
    );
  }

  const density = scene.peak_density;
  const status =
    density >= 5 ? "CRITICAL" : density >= 3.5 ? "HIGH" : density >= 2 ? "MODERATE" : "SAFE";

  out.unshift(
    `Status: ${status}. Peak crowd ${scene.peak_count} people, peak density ${density.toFixed(1)} people/m^2.`
  );

  if (urgent.length === 0) {
    out.push(
      "No active emergencies. Crowd density is within safe operating range — maintain normal monitoring."
    );
  }

  return [...urgent, ...out].join("\n");
}
