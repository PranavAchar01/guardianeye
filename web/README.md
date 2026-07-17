# GuardianEye Live

Next.js web app that presents GuardianEye's stadium-safety detection and layers
a **Lyzr**-powered AI safety officer on top of the real detection telemetry.

- Embedded showcase video (crowd counting, collapse detection, edge-fall watch).
- Per-feed **AI Safety Briefing**: the Lyzr agent reads the density / incident /
  edge-event telemetry and recommends operator actions.
- **Ask the safety officer**: natural-language Q&A across all feeds.

The app works with zero config (deterministic on-device analysis) and goes fully
live when a Lyzr API key is present.

## Environment

| Var | Required | Purpose |
|-----|----------|---------|
| `LYZR_API_KEY` | for live AI | Lyzr Agent API key (agent-prod.studio.lyzr.ai) |
| `LYZR_AGENT_ID` | optional | reuse a specific agent; auto-created if unset |
| `LYZR_MODEL` | optional | default `gpt-4o-mini` |

Telemetry is regenerated from run outputs with `node scripts/build_web_events.mjs`.
