import type { ReactNode } from "react";

interface Props {
  title: string;
  ariaLabel: string;
  isLoading: boolean;
  isError: boolean;
  count: number;
  emptyText: string;
  onRetry: () => void;
  icon?: ReactNode;
  accentClass?: string;
  children?: ReactNode;
}

export function SectionShell(props: Props): JSX.Element {
  const { title, ariaLabel, isLoading, isError, count, emptyText, onRetry, icon, accentClass, children } = props;
  return (
    <section
      role="region"
      aria-label={ariaLabel}
      className={`rounded-lg border bg-white/40 p-3 ${accentClass ?? ""}`}
    >
      <header className="mb-2 flex items-center gap-2">
        {icon}
        <h2 className="font-semibold text-base">{title}</h2>
        <span className="text-slate-500 text-xs" aria-label="count">
          ({count})
        </span>
      </header>
      {isLoading ? (
        <p className="text-slate-500 text-sm" role="status">
          Loading…
        </p>
      ) : isError ? (
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="text-red-700">Something went wrong.</span>
          <button
            type="button"
            onClick={onRetry}
            className="rounded bg-red-50 px-2 py-1 text-red-700 text-xs hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      ) : count === 0 ? (
        <p className="text-slate-500 text-sm">{emptyText}</p>
      ) : (
        <ul className="flex flex-col gap-2">{children}</ul>
      )}
    </section>
  );
}
