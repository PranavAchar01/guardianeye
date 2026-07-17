import { events } from "@/lib/analysis";
import { lyzrConfigured } from "@/lib/lyzr";
import Dashboard from "@/components/Dashboard";

export default function Home() {
  return <Dashboard scenes={events.scenes} lyzrLive={lyzrConfigured()} />;
}
