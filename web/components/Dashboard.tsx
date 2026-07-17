"use client";

import { useState } from "react";
import type { Scene } from "@/lib/analysis";

const RED = "#eb5050";

function Sparkline({ data, color = RED }: { data: number[]; color?: string }) {
  if (!data.length) return null;
  const w = 320;
  const h = 56;
  const max = Math.max(...data, 1);
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - (v / max) * (h - 6)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={2} />
    </svg>
  );
}

const LEVEL_COLOR: Record<string, string> = {
  SAFE: "#6ec86e",
  MODERATE: "#e5c04a",
  HIGH: "#e08a3c",
  CRITICAL: RED,
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#12151b] px-4 py-3">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-[#9aa0aa]">{label}</div>
    </div>
  );
}

export default function Dashboard({
  scenes,
  lyzrLive,
}: {
  scenes: Scene[];
  lyzrLive: boolean;
}) {
  const [active, setActive] = useState(0);
  const [briefings, setBriefings] = useState<Record<string, { text: string; source: string }>>({});
  const [loading, setLoading] = useState<string | null>(null);
  const [chat, setChat] = useState<{ role: "you" | "officer"; text: string }[]>([]);
  const [q, setQ] = useState("");
  const [asking, setAsking] = useState(false);

  const scene = scenes[active];
  const eventCount =
    scene.incidents.length + scene.edge_events.length + scene.crush_episodes.length;

  async function generate(sceneId: string) {
    setLoading(sceneId);
    try {
      const res = await fetch("/api/briefing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sceneId }),
      });
      const data = await res.json();
      setBriefings((b) => ({ ...b, [sceneId]: { text: data.briefing, source: data.source } }));
    } catch {
      setBriefings((b) => ({
        ...b,
        [sceneId]: { text: "Could not reach the briefing service.", source: "offline" },
      }));
    } finally {
      setLoading(null);
    }
  }

  async function ask() {
    const question = q.trim();
    if (!question || asking) return;
    setChat((c) => [...c, { role: "you", text: question }]);
    setQ("");
    setAsking(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, sessionId: "operator-chat" }),
      });
      const data = await res.json();
      setChat((c) => [...c, { role: "officer", text: data.answer }]);
    } catch {
      setChat((c) => [...c, { role: "officer", text: "The safety officer is unreachable." }]);
    } finally {
      setAsking(false);
    }
  }

  const brief = briefings[scene.id];

  return (
    <main className="mx-auto max-w-5xl px-5 pb-24">
      {/* Hero */}
      <header className="pt-14 pb-8 text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-[#1a1e26] px-3 py-1 text-xs">
          <span className={`h-2 w-2 rounded-full pulse ${lyzrLive ? "bg-[#6ec86e]" : "bg-[#e08a3c]"}`} />
          {lyzrLive ? "Lyzr AI safety officer: LIVE" : "Lyzr AI: connect a key to go live"}
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl">GUARDIANEYE</h1>
        <p className="mt-3 text-xl font-semibold" style={{ color: RED }}>
          The AI safety officer for stadiums
        </p>
        <p className="mx-auto mt-3 max-w-2xl text-[#9aa0aa]">
          Crowd crush, collapse, and edge-fall detection from ordinary stadium
          video — with a Lyzr-powered agent that reads the telemetry and tells
          the control room what to do.
        </p>
      </header>

      {/* Demo video */}
      <section className="overflow-hidden rounded-2xl border border-[#242a34] bg-black">
        <video
          controls
          playsInline
          preload="metadata"
          poster="/poster.jpg"
          className="w-full"
          src="/showcase.mp4"
        />
      </section>
      <p className="mt-2 text-center text-xs text-[#9aa0aa]">
        Real footage: packed stadium (2,000+ fans counted live) · collapse
        detection · drone edge-fall watch. Every frame is GuardianEye output.
      </p>

      {/* Scene tabs */}
      <section className="mt-12">
        <div className="flex flex-wrap gap-2">
          {scenes.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setActive(i)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                i === active ? "bg-[#eb5050] text-black" : "bg-[#1a1e26] text-[#e8e8e8]"
              }`}
            >
              {s.title}
            </button>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-[#242a34] bg-[#14181f] p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="text-2xl font-bold">{scene.title}</h2>
              <p className="text-sm text-[#9aa0aa]">{scene.venue}</p>
            </div>
            <span
              className="rounded-md px-3 py-1 text-sm font-bold text-black"
              style={{ background: LEVEL_COLOR[scene.worst_level] ?? RED }}
            >
              {scene.worst_level}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="peak people in frame" value={scene.peak_count.toLocaleString()} />
            <Stat label="peak density (p/m²)" value={scene.peak_density.toFixed(1)} />
            <Stat
              label="safety events"
              value={String(eventCount)}
            />
            <Stat label="depth source" value={scene.depth_source} />
          </div>

          <div className="mt-5">
            <div className="mb-1 text-xs text-[#9aa0aa]">crowd density over time (people/m²)</div>
            <Sparkline data={scene.density_series} />
          </div>

          <p className="mt-4 text-xs text-[#6f757f]">Pipeline: {scene.model}</p>

          {/* AI briefing */}
          <div className="mt-6 rounded-xl border border-[#2a2f3a] bg-[#0f1217] p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold tracking-wide text-white">
                AI SAFETY BRIEFING
              </h3>
              <button
                onClick={() => generate(scene.id)}
                disabled={loading === scene.id}
                className="rounded-md bg-[#eb5050] px-3 py-1.5 text-xs font-bold text-black disabled:opacity-50"
              >
                {loading === scene.id ? "Analyzing…" : brief ? "Regenerate" : "Generate briefing"}
              </button>
            </div>
            {brief ? (
              <div className="mt-3 whitespace-pre-line text-sm leading-relaxed text-[#dfe3ea]">
                {brief.text}
                <div className="mt-3 text-xs text-[#6f757f]">
                  {brief.source === "lyzr"
                    ? "— generated live by the Lyzr safety-officer agent"
                    : "— deterministic on-device analysis (connect Lyzr for live AI)"}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-[#9aa0aa]">
                Click “Generate briefing” to have the safety officer read this
                feed’s telemetry and recommend actions.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Ask the safety officer */}
      <section className="mt-12">
        <h2 className="text-xl font-bold">Ask the safety officer</h2>
        <p className="mt-1 text-sm text-[#9aa0aa]">
          Natural-language questions across all three feeds, answered from the
          live telemetry.
        </p>
        <div className="mt-4 rounded-2xl border border-[#242a34] bg-[#14181f] p-4">
          <div className="scrollbar-thin max-h-72 space-y-3 overflow-y-auto">
            {chat.length === 0 && (
              <p className="text-sm text-[#6f757f]">
                Try: “Which feed is most dangerous right now?” or “What should I
                do about the edge-fall risk?”
              </p>
            )}
            {chat.map((m, i) => (
              <div key={i} className={m.role === "you" ? "text-right" : "text-left"}>
                <div
                  className={`inline-block max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-sm ${
                    m.role === "you"
                      ? "bg-[#eb5050] text-black"
                      : "bg-[#1a1e26] text-[#dfe3ea]"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {asking && <p className="text-sm text-[#6f757f]">Safety officer is thinking…</p>}
          </div>
          <div className="mt-3 flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="Ask about crowd density, incidents, or fall risks…"
              className="flex-1 rounded-lg bg-[#0f1217] px-3 py-2 text-sm text-white outline-none placeholder:text-[#6f757f]"
            />
            <button
              onClick={ask}
              disabled={asking}
              className="rounded-lg bg-[#eb5050] px-4 py-2 text-sm font-bold text-black disabled:opacity-50"
            >
              Ask
            </button>
          </div>
        </div>
      </section>

      <footer className="mt-16 border-t border-[#242a34] pt-6 text-center text-sm text-[#6f757f]">
        Every stadium already owns the cameras. GuardianEye is the software that
        watches back.
        <br />
        <a
          href="https://github.com/PranavAchar01/guardianeye"
          className="text-[#eb5050]"
          target="_blank"
          rel="noreferrer"
        >
          github.com/PranavAchar01/guardianeye
        </a>{" "}
        · AI by Lyzr · anonymous by design, no faces stored
      </footer>
    </main>
  );
}
