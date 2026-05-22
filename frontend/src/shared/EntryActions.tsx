interface EntryActionsProps {
  onEdit: () => void;
  onDelete: () => void;
  busy?: boolean;
}

export function EntryActions({ onEdit, onDelete, busy }: EntryActionsProps): JSX.Element {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onEdit}
        disabled={busy}
        aria-label="Edit entry"
        title="Edit"
        className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
      >
        <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M14.5 2.5l3 3-9 9H5.5v-3l9-9z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={busy}
        aria-label="Delete entry"
        title="Delete"
        className="rounded p-1 text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
      >
        <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M4 6h12M8 6V4h4v2m-6 0v10a1 1 0 001 1h6a1 1 0 001-1V6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
