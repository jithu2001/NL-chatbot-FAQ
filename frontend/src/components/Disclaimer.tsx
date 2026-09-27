export default function Disclaimer() {
  return (
    <section
      aria-label="Disclaimer"
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
    >
      <p className="flex items-center gap-2 text-sm font-semibold">
        <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 shrink-0 fill-current">
          <path d="M10 1.5 3 4.3v5.2c0 4.3 3 8.2 7 9 4-.8 7-4.7 7-9V4.3L10 1.5Zm-1 12.3L5.8 10.6l1.3-1.3L9 11.2l3.9-3.9 1.3 1.3L9 13.8Z" />
        </svg>
        Facts-only. No investment advice.
      </p>
      <p className="mt-1 text-xs leading-relaxed text-amber-800/90 dark:text-amber-100/80">
        Information is provided from publicly available official AMC (PPFAS Mutual Fund, HDFC Mutual Fund) and AMFI sources. Always verify the
        latest official scheme documents.
      </p>
    </section>
  );
}
