import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { groupByAmc, type SchemeInfo } from "../api/chat";

const MAX_LENGTH = 500;

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
  schemes: SchemeInfo[];
  scheme: string;
  onSchemeChange: (scheme: string) => void;
}

export default function ChatInput({ onSubmit, disabled, schemes, scheme, onSchemeChange }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      {schemes.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <label htmlFor="scheme" className="font-medium">
            Scheme
          </label>
          <select
            id="scheme"
            value={scheme}
            onChange={(e) => onSchemeChange(e.target.value)}
            className="min-w-0 max-w-full flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 sm:flex-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:ring-brand-500/30"
          >
            <option value="">Auto (detect from question)</option>
            {groupByAmc(schemes).map(([amc, list]) => (
              <optgroup key={amc} label={amc}>
                {list.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} — {s.category}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      )}
      <div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-200 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:ring-brand-500/30">
        <label htmlFor="question" className="sr-only">
          Ask a factual question
        </label>
        <textarea
          id="question"
          ref={ref}
          rows={1}
          value={value}
          maxLength={MAX_LENGTH}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a factual question..."
          autoComplete="off"
          className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-[15px] leading-6 placeholder:text-slate-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Send question"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-800 text-white transition hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300 dark:disabled:bg-slate-700"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" className="h-5 w-5 fill-current">
            <path d="M3.1 2.6a.75.75 0 0 1 .8-.1l13.5 6.8a.75.75 0 0 1 0 1.4L3.9 17.5a.75.75 0 0 1-1-.9L4.7 10 2.9 3.4a.75.75 0 0 1 .2-.8ZM6.1 10.75l-1.2 4.4L14.6 10 4.9 4.85l1.2 4.4h5.15a.75.75 0 0 1 0 1.5H6.1Z" />
          </svg>
        </button>
      </div>
      <p className="px-1 text-[11px] text-slate-500 dark:text-slate-400">
        Please don't share PAN, Aadhaar, folio or account numbers, OTPs, phone numbers or email addresses.
      </p>
    </form>
  );
}
