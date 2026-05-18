import { useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { DateBar } from "@/features/date/DateBar";
import { SelectedDateProvider, useSelectedDate } from "@/features/date/useSelectedDate";
import { AppointmentsSection } from "@/features/appointments/AppointmentsSection";
import { FeedsSection } from "@/features/feeds/FeedsSection";
import { PoopsSection } from "@/features/poops/PoopsSection";
import { SleepsSection } from "@/features/sleeps/SleepsSection";
import { queryKeys } from "@/shared/queryKeys";

const ChatPanel = lazy(() =>
  import("@/features/chat/ChatPanel").then((m) => ({ default: m.ChatPanel })),
);

const SECTION_KEYS = new Set(["feeds", "sleeps", "poops", "appointments"]);

function RefreshButton(): JSX.Element {
  const qc = useQueryClient();
  const { date } = useSelectedDate();
  const onClick = () => {
    for (const key of queryKeys.allForDate(date)) {
      qc.invalidateQueries({ queryKey: key });
    }
    // Also catch any stale keys for past dates the user might have navigated through.
    qc.invalidateQueries({
      predicate: (q) => typeof q.queryKey[0] === "string" && SECTION_KEYS.has(q.queryKey[0]),
    });
  };
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Refresh all sections"
      className="rounded bg-slate-200 px-2 py-1 text-sm hover:bg-slate-300"
    >
      ⟳
    </button>
  );
}

function AppShell(): JSX.Element {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 p-4 pb-32">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">MomDiary</h1>
        <div className="flex items-center gap-2">
          <DateBar />
          <RefreshButton />
        </div>
      </header>
      <FeedsSection />
      <SleepsSection />
      <PoopsSection />
      <AppointmentsSection />
      <footer className="fixed inset-x-0 bottom-0 mx-auto max-w-md">
        <Suspense fallback={<div className="p-4 text-slate-500 text-sm">Loading chat…</div>}>
          <ChatPanel />
        </Suspense>
      </footer>
    </main>
  );
}

export default function App(): JSX.Element {
  return (
    <SelectedDateProvider>
      <AppShell />
    </SelectedDateProvider>
  );
}
