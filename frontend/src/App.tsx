import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/AuthShell";
import { useLogoutMutation, useSession } from "@/features/auth/useSession";
import { BabySwitcher } from "@/features/babies/BabySwitcher";
import { FirstBabyPrompt } from "@/features/babies/FirstBabyPrompt";
import { ChatProvider } from "@/features/chat/ChatContext";
import { SelectedDateProvider } from "@/features/date/useSelectedDate";
import { FeedHistoryPage } from "@/features/home/FeedHistoryPage";
import { HomePage } from "@/features/home/HomePage";

const CHAT_VISIBLE_STORAGE_KEY = "momdiary.chatVisible";

const ChatPanel = lazy(() =>
  import("@/features/chat/ChatPanel").then((m) => ({ default: m.ChatPanel })),
);

function ProfileMenu(props: { displayName: string }): JSX.Element {
  const logout = useLogoutMutation();
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-600">{props.displayName}</span>
      <button
        type="button"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
        className="rounded bg-white px-2 py-1 text-slate-700 ring-1 ring-slate-200 hover:bg-amber-50 disabled:opacity-60"
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
    if (typeof window === "undefined") return false;
    const stored = window.localStorage.getItem(CHAT_VISIBLE_STORAGE_KEY);
    return stored === "true";
  });

  // Drives the in-app "page" the caregiver sees. We deliberately keep this in
  // local state (no router) — the app is currently a single-pane mobile flow
  // and adding react-router for one drill-down would be over-engineering.
  const [view, setView] = useState<"home" | "feedHistory">("home");

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(CHAT_VISIBLE_STORAGE_KEY, String(chatVisible));
  }, [chatVisible]);

  const hideChat = useCallback(() => setChatVisible(false), []);
  const showChat = useCallback(() => setChatVisible(true), []);

  return (
    <div className="min-h-screen bg-amber-50">
      {/* Small utility strip above the home view so the caregiver can still
          switch babies and sign out without leaving the dashboard. */}
      <div className="mx-auto flex w-full max-w-md items-center justify-between gap-2 px-4 pt-3">
        <BabySwitcher activeBabyId={props.activeBabyId} />
        <ProfileMenu displayName={props.displayName} />
      </div>

      {view === "home" ? (
        <HomePage
          activeBabyId={props.activeBabyId}
          onOpenChat={showChat}
          onOpenFeedHistory={() => setView("feedHistory")}
        />
      ) : (
        <FeedHistoryPage onBack={() => setView("home")} />
      )}

      {chatVisible ? (
        <div
          className="fixed right-4 bottom-20 z-30 w-[min(calc(100vw-2rem),26rem)] origin-bottom-right animate-[chatPop_180ms_ease-out]"
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
          className="fixed right-4 bottom-20 z-30 grid h-14 w-14 place-items-center rounded-full bg-amber-500 text-2xl text-white shadow-lg ring-4 ring-amber-200 hover:bg-amber-600"
        >
          💬
        </button>
      )}
    </div>
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
      <ChatProvider>
        <AppShell displayName={user.display_name} activeBabyId={user.active_baby_id} />
      </ChatProvider>
    </SelectedDateProvider>
  );
}

export default function App(): JSX.Element {
  return <AuthGate />;
}
