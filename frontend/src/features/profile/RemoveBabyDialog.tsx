import { useEffect, useRef } from "react";
import { ApiError } from "@/shared/apiClient";
import type { Baby } from "@/shared/types";
import { useDeleteBabyMutation } from "../babies/useBabies";

/**
 * Explicit destructive-confirmation dialog for soft-deleting a baby.
 *
 * The dialog plainly names the consequence (all data hidden) and disables
 * the destructive button while the request is in flight. Cancel closes
 * without calling the mutation. Enter does NOT auto-submit — the user must
 * deliberately click Remove. (FR-014..FR-018, research §R4.)
 */
export function RemoveBabyDialog(props: {
  baby: Baby;
  onClose: () => void;
}): JSX.Element {
  const { baby, onClose } = props;
  const del = useDeleteBabyMutation();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);

  // Focus the (safe) Cancel button when the dialog opens.
  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  // Esc closes (when not in flight).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !del.isPending) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [del.isPending, onClose]);

  const confirm = () => {
    del.mutate(baby.id, {
      onSuccess: () => onClose(),
    });
  };

  const error = del.error instanceof ApiError ? del.error.message : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`remove-baby-${baby.id}-title`}
      aria-describedby={`remove-baby-${baby.id}-body`}
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
      onClick={() => {
        if (!del.isPending) onClose();
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl"
      >
        <h2
          id={`remove-baby-${baby.id}-title`}
          className="text-lg font-semibold text-slate-900"
        >
          Remove {baby.display_name}?
        </h2>
        <p
          id={`remove-baby-${baby.id}-body`}
          className="mt-2 text-sm text-slate-600"
        >
          This will hide {baby.display_name}&apos;s profile and all of{" "}
          {baby.display_name}&apos;s feeds, sleeps, diapers, and appointments
          from every view. You won&apos;t be able to undo this from the app.
        </p>
        {error ? (
          <p role="alert" aria-live="polite" className="mt-3 text-sm text-red-600">
            {error}
          </p>
        ) : null}
        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            ref={cancelRef}
            onClick={onClose}
            disabled={del.isPending}
            className="rounded bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={del.isPending}
            className="rounded bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60"
          >
            {del.isPending ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
