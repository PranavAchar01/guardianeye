import { NextRequest, NextResponse } from "next/server";
import { allTelemetry } from "@/lib/analysis";
import { lyzrChat } from "@/lib/lyzr";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const { question, sessionId } = (await req.json().catch(() => ({}))) as {
    question?: string;
    sessionId?: string;
  };
  if (!question || !question.trim()) {
    return NextResponse.json({ error: "empty question" }, { status: 400 });
  }

  const apiKey = process.env.LYZR_API_KEY;
  if (!apiKey) {
    return NextResponse.json({
      answer:
        "The live AI safety officer needs a Lyzr API key to be configured. " +
        "Once connected, ask me anything about the crowd density, incidents, " +
        "or edge-fall risks across the three monitored feeds.",
      source: "offline",
    });
  }

  try {
    const message =
      `Operator question: ${question.trim()}\n\n` +
      "Answer using only the telemetry below, across all three monitored feeds. " +
      "Be concise and operational.\n\n" +
      allTelemetry();
    const answer = await lyzrChat({
      apiKey,
      message,
      sessionId: sessionId?.trim() || "operator-chat",
    });
    return NextResponse.json({ answer, source: "lyzr" });
  } catch (err) {
    return NextResponse.json({
      answer:
        "The AI safety officer is temporarily unreachable. Telemetry is still " +
        "available in the briefing panels above.",
      source: "offline",
      note: err instanceof Error ? err.message : "lyzr unavailable",
    });
  }
}
