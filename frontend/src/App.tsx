import { useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/AuthShell";
import { useLogoutMutation, useSession } from "@/features/auth/useSession";
import { BabySwitcher } from "@/features/babies/BabySwitcher";
import { FirstBabyPrompt } from "@/features/babies/FirstBabyPrompt";
import { DateBar } from "@/features/date/DateBar";
import { SelectedDateProvider, useSelectedDate } from "@/features/date/useSelectedDate";
import { AppointmentsSection } from "@/features/appointments/AppointmentsSection";
import { FeedsSection } from "@/features/feeds/FeedsSection";
import { PoopsSection } from "@/features/poops/PoopsSection";
import { SleepsSection } from "@/features/sleeps/SleepsSection";
import { queryKeys } from "@/shared/queryKeys";

const CHAT_VISIBLE_STORAGE_KEY = "momdiary.chatVisible";

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

function ProfileMenu(props: { displayName: string }): JSX.Element {
  const logout = useLogoutMutation();
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-slate-700">{props.displayName}</span>
      <button
        type="button"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
        className="rounded bg-slate-200 px-2 py-1 hover:bg-slate-300 disabled:opacity-60"
      >
        {logout.isPending ? "…" : "Sign out"}
      </button>
    </div>
  );
}

function AppShell(props: {
  displayName: string;
  activeBabyId: number;
}): JSX.Element {
  const [chatVisible, setChatVisible] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem(CHAT_VISIBLE_STORAGE_KEY);
    return stored === null ? true : stored === "true";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(CHAT_VISIBLE_STORAGE_KEY, String(chatVisible));
  }, [chatVisible]);

  const hideChat = useCallback(() => setChatVisible(false), []);
  const showChat = useCallback(() => setChatVisible(true), []);

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-4 p-4 pb-24">
      <header className="relative flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">MomDiary</h1>
          <ProfileMenu displayName={props.displayName} />
        </div>
        <div className="flex items-center justify-between">
          <BabySwitcher activeBabyId={props.activeBabyId} />
          <div className="flex items-center gap-2">
            <DateBar />
            <RefreshButton />
          </div>
        </div>
      </header>
      <FeedsSection />
      <SleepsSection />
      <PoopsSection />
      <AppointmentsSection />
      {chatVisible ? (
        <div
          className="fixed right-4 bottom-4 z-20 w-[min(calc(100vw-2rem),26rem)] origin-bottom-right animate-[chatPop_180ms_ease-out]"
          role="dialog"
          aria-label="Chat"
        >
          <Suspense fallback={<div className="p-4 text-slate-500 text-sm">Loading chat…</div>}>
            <ChatPanel onHide={hideChat} />
          </Suspense>
        </div>
      ) : (
        <button
          type="button"
          onClick={showChat}
          aria-label="Show chat"
          className="fixed right-4 bottom-4 z-20 rounded-full bg-slate-900 px-4 py-3 text-sm text-white shadow-lg hover:bg-slate-700"
        >
          💬 Chat
        </button>
      )}
    </main>
  );
}

function AuthGate(): JSX.Element {
  const session = useSession();

  if (session.isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center text-slate-500">
        Loading…
      </main>
    );
  }

  const user = session.data?.user;
  if (!user) return <AuthShell />;

  if (user.active_baby_id == null) return <FirstBabyPrompt />;

  return (
    <SelectedDateProvider>
      <AppShell displayName={user.display_name} activeBabyId={user.active_baby_id} />
    </SelectedDateProvider>
  );
}

export default function App(): JSX.Element {
  return <AuthGate />;
}
