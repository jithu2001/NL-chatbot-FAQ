import Lozenge from "@atlaskit/lozenge";
import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "../api/chat";

/** Small development-only indicator for the AI model and the knowledge base. */
export default function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    const load = () => getHealth().then((h) => alive && setHealth(h));
    load();
    const timer = window.setInterval(load, 30_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  if (health === undefined) return null;
  const item = (label: string, ok: boolean) => (
    <Lozenge appearance={ok ? "success" : "removed"}>
      {label} {ok ? "✓" : "✗"}
    </Lozenge>
  );
  return (
    <span className="dev-status" title="Development status">
      {health ? (
        <>
          {item("AI model", health.llm)}
          {item("Knowledge base", health.chromadb)}
        </>
      ) : (
        item("Backend", false)
      )}
    </span>
  );
}
