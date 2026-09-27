import type { ChatResponse } from "../api/chat";
import SourceCitation from "./SourceCitation";

export type Message =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; response: ChatResponse }
  | { id: string; role: "error"; text: string };

const BADGES: Record<string, { label: string; className: string } | undefined> = {
  ADVICE: { label: "No investment advice", className: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-100" },
  UNSUPPORTED: { label: "No predictions", className: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-100" },
  PII: { label: "Personal data blocked", className: "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100" },
};

function AssistantCard({ response }: { response: ChatResponse }) {
  const badge = BADGES[response.classification];
  return (
    <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      {badge && (
        <span className={`mb-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.className}`}>
          {badge.label}
        </span>
      )}
      <p className="whitespace-pre-line leading-relaxed">{response.answer}</p>
      {response.scheme && response.classification === "FACTUAL" && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          Scheme: <span className="font-medium text-slate-700 dark:text-slate-200">{response.scheme}</span>
          {response.scheme_defaulted && " (no scheme named — name a scheme or pick one below to ask about another)"}
        </p>
      )}
      {response.source && <SourceCitation source={response.source} />}
    </div>
  );
}

export default function ChatMessage({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] sm:max-w-[75%]">
          <p className="mb-1 text-right text-xs font-medium text-slate-500 dark:text-slate-400">You</p>
          <p className="rounded-2xl rounded-tr-sm bg-brand-800 px-4 py-2.5 leading-relaxed text-white shadow-sm dark:bg-brand-700">
            {message.text}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%] sm:max-w-[80%]">
        <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">Assistant</p>
        {message.role === "assistant" ? (
          <AssistantCard response={message.response} />
        ) : (
          <div
            role="alert"
            className="rounded-2xl rounded-tl-sm border border-slate-300 bg-slate-100 px-4 py-3 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          >
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}
