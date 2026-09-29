import PageIcon from "@atlaskit/icon/core/page";
import Link from "@atlaskit/link";
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
    <div className="source-card">
      <span className="source-icon" aria-hidden="true">
        <PageIcon label="" color="var(--ds-icon-brand)" />
      </span>
      <div className="source-details">
        <div className="source-label">Source</div>
        <div className="source-title">
          <Link href={sourceHref(source)} target="_blank">
            {source.title}
            {source.page ? `, p. ${source.page}` : ""}
          </Link>
        </div>
        <div className="source-meta">
          <span>
            {source.source_type} · {source.authority}
          </span>
          <span>Last updated from sources: {formatDate(source.last_updated)}</span>
          {!hasOfficialDate && <span>Source retrieved: {formatDate(source.retrieved_date)}</span>}
        </div>
      </div>
    </div>
  );
}
