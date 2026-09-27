import { useEffect, useRef, useState } from "react";
import { ApiError, askQuestion, getSchemes, type SchemeInfo } from "./api/chat";
import ChatInput from "./components/ChatInput";
import ChatMessage, { type Message } from "./components/ChatMessage";
import Disclaimer from "./components/Disclaimer";
import ExampleQuestions from "./components/ExampleQuestions";
import HealthStatus from "./components/HealthStatus";

let nextId = 0;
const newId = () => `m${++nextId}`;

export default function App() {
  // Conversation lives only in memory: nothing is persisted or sent anywhere else.
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [schemes, setSchemes] = useState<SchemeInfo[]>([]);
  const [scheme, setScheme] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSchemes().then(setSchemes);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function ask(question: string) {
    if (loading) return;
    setMessages((m) => [...m, { id: newId(), role: "user", text: question }]);
    setLoading(true);
    try {
      const response = await askQuestion(question, scheme || null);
      setMessages((m) => [...m, { id: newId(), role: "assistant", response }]);
    } catch (err) {
      const text = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setMessages((m) => [...m, { id: newId(), role: "error", text }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-lg" />
            <div>
              <h1 className="text-lg font-bold leading-tight text-brand-900 dark:text-white">PowerUp Money</h1>
              <p className="text-sm leading-tight text-slate-600 dark:text-slate-300">Mutual Fund FAQ Assistant</p>
            </div>
          </div>
          {import.meta.env.DEV && <HealthStatus />}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-5 px-4 py-5 sm:px-6">
          <p className="text-[15px] text-slate-600 dark:text-slate-300">
            Get verified mutual-fund facts from official sources.
          </p>
          <Disclaimer />

          {messages.length === 0 && (
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="leading-relaxed">
                <span className="font-semibold">Welcome!</span> I answer factual questions about selected{" "}
                <span className="font-medium">PPFAS Mutual Fund</span> schemes, such as expense ratio, exit load,
                minimum SIP, lock-in, riskometer and benchmark, plus how to get statements. Every answer links to one
                official source.
              </p>
              {schemes.length > 0 && (
                <ul className="flex flex-wrap gap-1.5 text-xs">
                  {schemes.map((s) => (
                    <li key={s.name} className="rounded-md bg-slate-100 px-2 py-1 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                      {s.name}
                    </li>
                  ))}
                </ul>
              )}
              <ExampleQuestions onSelect={ask} disabled={loading} />
            </div>
          )}

          <div className="space-y-4" aria-live="polite">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400" role="status">
                <span
                  aria-hidden="true"
                  className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700 dark:border-slate-700 dark:border-t-brand-200"
                />
                Checking official sources...
              </div>
            )}
          </div>

          {messages.length > 0 && !loading && (
            <details className="text-sm text-slate-500 dark:text-slate-400">
              <summary className="cursor-pointer select-none">Example questions</summary>
              <div className="mt-2">
                <ExampleQuestions onSelect={ask} disabled={loading} />
              </div>
            </details>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <footer className="border-t border-slate-200 bg-white/95 dark:border-slate-800 dark:bg-slate-900/95">
        <div className="mx-auto max-w-3xl px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-6">
          <ChatInput onSubmit={ask} disabled={loading} schemes={schemes} scheme={scheme} onSchemeChange={setScheme} />
        </div>
      </footer>
    </div>
  );
}
