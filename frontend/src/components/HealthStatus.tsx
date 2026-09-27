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
    <span className="inline-flex items-center gap-1">
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-brand-500" : "bg-slate-400"}`} />
      {label} {ok ? "✓" : "✗"}
    </span>
  );
  return (
    <p className="hidden gap-3 text-[11px] text-slate-400 sm:flex dark:text-slate-500" title="Development status">
      {health ? (
        <>
          {item("AI model", health.llm)}
          {item("Knowledge Base", health.chromadb)}
        </>
      ) : (
        item("Backend", false)
      )}
    </p>
  );
}
