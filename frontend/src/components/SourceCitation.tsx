import type { SourceInfo } from "../api/chat";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function formatDate(value: string | null | undefined): string {
  if (!value || !ISO_DATE.test(value)) return "Not specified";
  const [y, m, d] = value.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function sourceHref(source: SourceInfo): string {
  // Open PDFs at the cited page. The base URL always comes from the registry.
  const isPdf = /\.pdf($|\?)/i.test(source.url);
  return isPdf && source.page ? `${source.url}#page=${source.page}` : source.url;
}

export default function SourceCitation({ source }: { source: SourceInfo }) {
  const hasOfficialDate = ISO_DATE.test(source.last_updated);
  return (
    <div className="mt-3 border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
      <p className="text-slate-700 dark:text-slate-200">
        <span className="font-medium">Source: </span>
        <a
          href={sourceHref(source)}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-brand-700 underline decoration-brand-200 underline-offset-2 hover:decoration-brand-600 dark:text-brand-200 dark:decoration-brand-500/50"
        >
          {source.title}
          {source.page ? `, p. ${source.page}` : ""}
          <span aria-hidden="true"> ↗</span>
          <span className="sr-only"> (opens official source in a new tab)</span>
        </a>
      </p>
      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
        {source.source_type} · {source.authority}
      </p>
      <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-300">
        Last updated from sources: <span className="font-medium">{formatDate(source.last_updated)}</span>
      </p>
      {!hasOfficialDate && (
        <p className="text-xs text-slate-500 dark:text-slate-400">Source retrieved: {formatDate(source.retrieved_date)}</p>
      )}
    </div>
  );
}
