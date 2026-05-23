import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/AuthShell";
import { useLogoutMutation, useSession } from "@/features/auth/useSession";
import { BabySwitcher } from "@/features/babies/BabySwitcher";
import { FirstBabyPrompt } from "@/features/babies/FirstBabyPrompt";
import { ChatProvider } from "@/features/chat/ChatContext";
import { SelectedDateProvider } from "@/features/date/useSelectedDate";
import { FeedHistoryPage } from "@/features/home/FeedHistoryPage";
import { HomePage } from "@/features/home/HomePage";
import { PoopHistoryPage } from "@/features/home/PoopHistoryPage";
import { SleepHistoryPage } from "@/features/home/SleepHistoryPage";
import { AppointmentHistoryPage } from "@/features/home/AppointmentHistoryPage";

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
  // When the caregiver opens the chat via the bottom "Voice" tab the panel
  // becomes a voice-only experience (no textarea, every utterance is sent to
  // the research API). We just flag it for one open and ChatPanel consumes
  // it on mount.
  const [chatVoiceOnly, setChatVoiceOnly] = useState(false);

  // Drives the in-app "page" the caregiver sees. We deliberately keep this in
  // local state (no router) — the app is currently a single-pane mobile flow
  // and adding react-router for one drill-down would be over-engineering.
  const [view, setView] = useState<
    "home" | "feedHistory" | "poopHistory" | "sleepHistory" | "appointmentHistory"
  >("home");

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(CHAT_VISIBLE_STORAGE_KEY, String(chatVisible));
  }, [chatVisible]);

  // Pre-load the ChatPanel chunk so that opening the chat (especially via
  // the bottom "Voice" tab, which auto-starts the mic) happens synchronously
  // and stays within the browser's user-gesture window. Without this the
  // dynamic import resolves after the click tick, which Chrome treats as
  // outside the gesture for SpeechRecognition.start() — the mic then never
  // actually listens.
  useEffect(() => {
    void import("@/features/chat/ChatPanel");
  }, []);

  const hideChat = useCallback(() => {
    setChatVisible(false);
    setChatVoiceOnly(false);
  }, []);
  const showChat = useCallback(() => {
    setChatVoiceOnly(false);
    setChatVisible(true);
  }, []);
  const showVoice = useCallback(() => {
    setChatVoiceOnly(true);
    setChatVisible(true);
  }, []);

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
          onOpenVoice={showVoice}
          onOpenFeedHistory={() => setView("feedHistory")}
          onOpenPoopHistory={() => setView("poopHistory")}
          onOpenSleepHistory={() => setView("sleepHistory")}
          onOpenAppointmentHistory={() => setView("appointmentHistory")}
        />
      ) : view === "feedHistory" ? (
        <FeedHistoryPage onBack={() => setView("home")} />
      ) : view === "poopHistory" ? (
        <PoopHistoryPage onBack={() => setView("home")} />
      ) : view === "sleepHistory" ? (
        <SleepHistoryPage onBack={() => setView("home")} />
      ) : (
        <AppointmentHistoryPage onBack={() => setView("home")} />
      )}

      {chatVisible ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Chat"
          className="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 sm:items-center"
          onClick={hideChat}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md origin-bottom animate-[chatPop_180ms_ease-out]"
          >
            <Suspense fallback={<div className="p-4 text-slate-500 text-sm">Loading chat…</div>}>
              <ChatPanel onHide={hideChat} voiceOnly={chatVoiceOnly} />
            </Suspense>
          </div>
        </div>
      ) : null}
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
