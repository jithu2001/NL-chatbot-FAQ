import Button from "@atlaskit/button/new";
import Heading from "@atlaskit/heading";
import RefreshIcon from "@atlaskit/icon/core/refresh";
import { useEffect, useRef, useState } from "react";
import { ApiError, askQuestion, getSchemes, groupByAmc, type SchemeInfo } from "./api/chat";
import ChatInput from "./components/ChatInput";
import ChatMessage, { LoadingEntry, type Message } from "./components/ChatMessage";
import Disclaimer from "./components/Disclaimer";
import ExampleQuestions from "./components/ExampleQuestions";
import HealthStatus from "./components/HealthStatus";

let nextId = 0;
const newId = () => `m${++nextId}`;

function EmptyState({ schemes, onAsk, disabled }: { schemes: SchemeInfo[]; onAsk: (q: string) => void; disabled: boolean }) {
  return (
    <section className="panel" aria-label="Getting started">
      <div className="panel-section">
        <Heading size="small" as="h2">
          What you can ask
        </Heading>
        <p>
          Factual questions about the schemes below — expense ratio, exit load, minimum SIP, lock-in, riskometer and
          benchmark — plus how to get account and capital-gains statements. Every answer links to one official source.
        </p>
        <ExampleQuestions onSelect={onAsk} disabled={disabled} />
      </div>
      {schemes.length > 0 && (
        <div className="panel-section">
          <Heading size="xsmall" as="h2">
            Schemes covered
          </Heading>
          <div className="scheme-groups">
            {groupByAmc(schemes).map(([amc, list]) => (
              <div key={amc}>
                <h3 className="scheme-group-title">{amc}</h3>
                <ul className="scheme-list">
                  {list.map((s) => (
                    <li key={s.name}>
                      <span>{s.name}</span>
                      <span className="scheme-category">{s.category}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

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
    <div className="app">
      <header className="top-nav">
        <div className="product">
          <img src="/favicon.svg" alt="" className="product-tile" />
          <span className="product-name">PowerUp Money</span>
          <span className="product-divider" aria-hidden="true" />
          <span className="product-area">Mutual Fund FAQ Assistant</span>
        </div>
        <div className="nav-actions">
          {import.meta.env.DEV && <HealthStatus />}
          {messages.length > 0 && (
            <Button appearance="subtle" iconBefore={RefreshIcon} isDisabled={loading} onClick={() => setMessages([])}>
              New conversation
            </Button>
          )}
        </div>
      </header>

      <main className="scroll-area">
        <div className="page">
          <div className="page-header">
            <Heading size="large" as="h1">
              Mutual Fund FAQ Assistant
            </Heading>
            <p>Get verified mutual-fund facts from official sources.</p>
          </div>

          <div className="stack-300">
            <Disclaimer />
            {messages.length === 0 && <EmptyState schemes={schemes} onAsk={ask} disabled={loading} />}
            {(messages.length > 0 || loading) && (
              <ol className="conversation" aria-live="polite" aria-label="Conversation">
                {messages.map((m) => (
                  <ChatMessage key={m.id} message={m} />
                ))}
                {loading && <LoadingEntry />}
              </ol>
            )}
          </div>
          <div ref={endRef} />
        </div>
      </main>

      <footer className="composer">
        <div className="composer-inner">
          <ChatInput onSubmit={ask} disabled={loading} schemes={schemes} scheme={scheme} onSchemeChange={setScheme} />
        </div>
      </footer>
    </div>
  );
}
