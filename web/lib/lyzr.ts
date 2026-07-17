/**
 * Minimal Lyzr Agent API client.
 *
 * Two calls are used:
 *   POST /v3/agents/template/single-task  -> create the safety-officer agent
 *   POST /v3/inference/chat/              -> run inference
 *
 * The app needs only ONE secret, LYZR_API_KEY. If LYZR_AGENT_ID is not set,
 * an agent is created on first use and cached for the life of the process.
 */

const BASE = process.env.LYZR_BASE_URL ?? "https://agent-prod.studio.lyzr.ai";
const PROVIDER_ID = process.env.LYZR_PROVIDER_ID ?? "OpenAI";
const MODEL = process.env.LYZR_MODEL ?? "gpt-4o-mini";
// Lyzr ships a managed OpenAI credential on new accounts under this id.
const CREDENTIAL_ID = process.env.LYZR_CREDENTIAL_ID ?? "lyzr_openai";

export const AGENT_ROLE =
  "You are the GuardianEye Safety Officer, an expert in stadium crowd safety " +
  "and emergency operations. You read structured computer-vision telemetry " +
  "(per-zone crowd density in people/m^2, person-down incidents, and " +
  "edge-fall risk events) and turn it into clear, decisive guidance for a " +
  "human control-room operator.";

export const AGENT_INSTRUCTIONS = [
  "Density thresholds (Fruin / G. Keith Still): >=2 moderate, >=3.5 high, >=5 critical people/m^2.",
  "Be concise and operational. Lead with the single most urgent action.",
  "Always name the affected zone(s) and the recommended response.",
  "Never invent events that are not in the telemetry. If a scene is calm, say so plainly.",
  "Use short paragraphs or tight bullet points a stressed operator can scan in seconds.",
  "Never identify individuals; this system is anonymous by design.",
].join(" ");

let cachedAgentId: string | null = process.env.LYZR_AGENT_ID ?? null;

function headers(apiKey: string) {
  return { "Content-Type": "application/json", "x-api-key": apiKey };
}

async function createAgent(apiKey: string): Promise<string> {
  const res = await fetch(`${BASE}/v3/agents/template/single-task`, {
    method: "POST",
    headers: headers(apiKey),
    body: JSON.stringify({
      name: "GuardianEye Safety Officer",
      description: "Turns GuardianEye CV telemetry into operator safety briefings.",
      agent_role: AGENT_ROLE,
      agent_instructions: AGENT_INSTRUCTIONS,
      agent_goal: "Keep the crowd safe by surfacing the right action at the right moment.",
      provider_id: PROVIDER_ID,
      model: MODEL,
      llm_credential_id: CREDENTIAL_ID,
      top_p: 0.9,
      temperature: 0.2,
    }),
  });
  if (!res.ok) {
    throw new Error(`Lyzr agent create failed (${res.status}): ${await res.text()}`);
  }
  const data = await res.json();
  const id = data.agent_id ?? data._id ?? data.id ?? data?.data?.agent_id;
  if (!id) throw new Error(`Lyzr agent create returned no id: ${JSON.stringify(data).slice(0, 300)}`);
  return id as string;
}

export async function ensureAgent(apiKey: string): Promise<string> {
  if (cachedAgentId) return cachedAgentId;
  cachedAgentId = await createAgent(apiKey);
  return cachedAgentId;
}

export async function lyzrChat(opts: {
  apiKey: string;
  message: string;
  sessionId: string;
  userId?: string;
}): Promise<string> {
  const agentId = await ensureAgent(opts.apiKey);
  const res = await fetch(`${BASE}/v3/inference/chat/`, {
    method: "POST",
    headers: headers(opts.apiKey),
    body: JSON.stringify({
      user_id: opts.userId ?? "guardianeye-web",
      agent_id: agentId,
      session_id: opts.sessionId,
      message: opts.message,
    }),
  });
  if (!res.ok) {
    throw new Error(`Lyzr inference failed (${res.status}): ${await res.text()}`);
  }
  const data = await res.json();
  const text =
    data.response ?? data.answer ?? data.message ?? data?.data?.response ?? data?.output;
  if (typeof text !== "string" || !text.trim()) {
    throw new Error(`Lyzr inference returned no text: ${JSON.stringify(data).slice(0, 300)}`);
  }
  return text.trim();
}

export function lyzrConfigured(): boolean {
  return Boolean(process.env.LYZR_API_KEY);
}
