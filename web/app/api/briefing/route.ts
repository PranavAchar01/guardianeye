import { NextRequest, NextResponse } from "next/server";
import { fallbackBriefing, sceneById, telemetry } from "@/lib/analysis";
import { lyzrChat } from "@/lib/lyzr";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const { sceneId } = (await req.json().catch(() => ({}))) as { sceneId?: string };
  const scene = sceneById(sceneId ?? "crowd");
  if (!scene) {
    return NextResponse.json({ error: "unknown scene" }, { status: 400 });
  }

  const apiKey = process.env.LYZR_API_KEY;
  const fallback = fallbackBriefing(scene);

  if (!apiKey) {
    return NextResponse.json({ briefing: fallback, source: "offline" });
  }

  try {
    const message =
      "Here is the current GuardianEye telemetry for one camera feed. " +
      "Give the control-room operator a safety briefing: lead with the most " +
      "urgent action, name affected zones, then a one-line overall status.\n\n" +
      telemetry(scene);
    const briefing = await lyzrChat({
      apiKey,
      message,
      sessionId: `briefing-${scene.id}`,
    });
    return NextResponse.json({ briefing, source: "lyzr" });
  } catch (err) {
    return NextResponse.json({
      briefing: fallback,
      source: "offline",
      note: err instanceof Error ? err.message : "lyzr unavailable",
    });
  }
}
