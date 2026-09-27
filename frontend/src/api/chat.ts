// Thin client for the FastAPI backend. All requests go to /api (proxied by Vite).

export type Classification = "FACTUAL" | "ADVICE" | "UNSUPPORTED" | "PII";

export interface SourceInfo {
  title: string;
  url: string;
  source_type: string;
  authority: string;
  last_updated: string;
  retrieved_date: string;
  page: number | null;
}

export interface ChatResponse {
  answer: string;
  classification: Classification;
  source: SourceInfo | null;
  last_updated: string | null;
  retrieved_date: string | null;
  scheme: string | null;
  scheme_defaulted: boolean;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  llm: boolean;
  chromadb: boolean;
}

export interface SchemeInfo {
  name: string;
  category: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {}

const SERVER_UNREACHABLE =
  "Couldn't reach the assistant server. Please make sure the backend is running and try again.";

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) return detail.message as string;
  } catch {
    /* fall through */
  }
  return res.status >= 500 ? "The assistant is temporarily unavailable. Please try again." : "Request failed.";
}

export async function askQuestion(question: string, scheme: string | null, signal?: AbortSignal): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      // The ngrok header skips ngrok's free-tier browser warning page for API calls.
      headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "1" },
      body: JSON.stringify({ question, scheme }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(SERVER_UNREACHABLE);
  }
  if (!res.ok) throw new ApiError(await readError(res));
  return (await res.json()) as ChatResponse;
}

export async function getHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { headers: { "ngrok-skip-browser-warning": "1" } });
    return res.ok ? ((await res.json()) as HealthResponse) : null;
  } catch {
    return null;
  }
}

export async function getSchemes(): Promise<SchemeInfo[]> {
  try {
    const res = await fetch(`${API_BASE}/api/schemes`, { headers: { "ngrok-skip-browser-warning": "1" } });
    return res.ok ? ((await res.json()) as SchemeInfo[]) : [];
  } catch {
    return [];
  }
}
