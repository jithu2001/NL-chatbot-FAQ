export const EXAMPLE_QUESTIONS = [
  "What is the expense ratio?",
  "What is the minimum SIP?",
  "How do I download my capital-gains statement?",
] as const;

interface Props {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export default function ExampleQuestions({ onSelect, disabled }: Props) {
  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Examples</h2>
      <ul className="mt-2 flex flex-wrap gap-2">
        {EXAMPLE_QUESTIONS.map((q) => (
          <li key={q}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(q)}
              className="rounded-full border border-brand-200 bg-white px-3.5 py-1.5 text-left text-sm text-brand-800 shadow-sm transition hover:border-brand-500 hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-brand-100 dark:hover:border-brand-500 dark:hover:bg-slate-800"
            >
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
