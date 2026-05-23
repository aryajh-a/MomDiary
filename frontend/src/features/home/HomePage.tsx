import { useMemo } from "react";
import { format, formatDistanceToNowStrict, parseISO } from "date-fns";
import { useFeeds } from "@/features/feeds/useFeeds";
import { useSleeps } from "@/features/sleeps/useSleeps";
import { usePoops } from "@/features/poops/usePoops";
import { useAppointments } from "@/features/appointments/useAppointments";
import { useBabies } from "@/features/babies/useBabies";
import { useChatContext } from "@/features/chat/ChatContext";
import { useSelectedDate } from "@/features/date/useSelectedDate";
import type {
  AppointmentEntry,
  FeedEntry,
  PoopEntry,
  SleepEntry,
} from "@/shared/types";

// -----------------------------------------------------------------------------
// HomePage — dashboard view matching the Home.jpeg mockup.
//
// Layout: header (greeting + baby name + "Ask AI" pill + bell) → stats card
// (Last feed / Sleep today / Next appt) → Quick log grid (Feed, Sleep, Poop,
// Appt, + More — Bath intentionally omitted per product) → Recent logs list →
// floating chat bubble (existing ChatPanel) → bottom tab bar (Home active).
//
// Quick-log tiles fire a templated NL message to the existing /v1/entries
// agent endpoint via `useChatContext().submit(...)`. The agent then asks for
// any missing fields in the chat panel, reusing the conversation thread.
// -----------------------------------------------------------------------------

interface HomePageProps {
  activeBabyId: number;
  onOpenChat: () => void;
  onOpenFeedHistory: () => void;
}

export function HomePage({ activeBabyId, onOpenChat, onOpenFeedHistory }: HomePageProps): JSX.Element {
  const babies = useBabies();
  const activeBaby = babies.data?.items.find((b) => b.id === activeBabyId);
  const babyName = activeBaby?.display_name ?? "baby";

  const { date } = useSelectedDate();
  const feeds = useFeeds(date);
  const sleeps = useSleeps(date);
  const poops = usePoops(date);
  const appts = useAppointments(date);

  const chat = useChatContext();
  const sendQuickLog = (message: string) => {
    onOpenChat();
    void chat.submit(message);
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-5 bg-amber-50 px-4 pt-6 pb-28 text-slate-900">
      <HomeHeader
        babyName={babyName}
        onAskAI={() => {
          onOpenChat();
        }}
      />
      <StatsCard
        feeds={feeds.data?.items ?? []}
        sleeps={sleeps.data?.items ?? []}
        appointments={appts.data?.items ?? []}
      />
      <QuickLogGrid
        onLog={sendQuickLog}
        onOpenChat={onOpenChat}
        onOpenFeedHistory={onOpenFeedHistory}
        disabled={chat.inFlight}
      />
      <RecentLogs
        feeds={feeds.data?.items ?? []}
        sleeps={sleeps.data?.items ?? []}
        poops={poops.data?.items ?? []}
        appointments={appts.data?.items ?? []}
        loading={feeds.isLoading || sleeps.isLoading || poops.isLoading || appts.isLoading}
      />
      <BottomTabBar />
    </main>
  );
}

// -----------------------------------------------------------------------------
// Header
// -----------------------------------------------------------------------------

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function HomeHeader(props: { babyName: string; onAskAI: () => void }): JSX.Element {
  return (
    <header className="flex items-start justify-between gap-3">
      <div className="flex flex-col">
        <span className="text-sm text-slate-500">{greeting()}</span>
        <h1 className="text-2xl font-bold leading-tight text-slate-900">
          Baby <span className="text-amber-700">{props.babyName}</span>
        </h1>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={props.onAskAI}
          className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-medium text-slate-800 shadow-sm ring-1 ring-slate-200 hover:bg-amber-50"
          aria-label="Ask AI"
        >
          <SparkleIcon className="h-4 w-4 text-amber-500" />
          Ask AI
        </button>
        <button
          type="button"
          className="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-600 shadow-sm ring-1 ring-slate-200 hover:bg-amber-50"
          aria-label="Notifications"
        >
          <BellIcon className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}

// -----------------------------------------------------------------------------
// Stats card
// -----------------------------------------------------------------------------

function StatsCard(props: {
  feeds: FeedEntry[];
  sleeps: SleepEntry[];
  appointments: AppointmentEntry[];
}): JSX.Element {
  const lastFeed = useMemo(() => {
    if (props.feeds.length === 0) return null;
    // Backend returns chronological asc; latest is the tail.
    return [...props.feeds].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)).at(-1)!;
  }, [props.feeds]);

  const sleepTotalMin = useMemo(
    () => props.sleeps.reduce((sum, s) => sum + s.duration_minutes, 0),
    [props.sleeps],
  );

  const nextAppt = useMemo(() => {
    const now = Date.now();
    const upcoming = props.appointments
      .filter((a) => new Date(a.scheduled_at).getTime() >= now)
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    return upcoming[0] ?? null;
  }, [props.appointments]);

  return (
    <section
      aria-label="Today at a glance"
      className="grid grid-cols-3 gap-2 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
    >
      <Stat
        label="Last feed"
        value={lastFeed ? formatRelative(lastFeed.occurred_at) : "—"}
        detail={lastFeed ? `${lastFeed.quantity}${lastFeed.unit} · ${shortFeed(lastFeed.feed_type)}` : "No feed yet"}
      />
      <div className="border-x border-slate-100">
        <Stat
          label="Sleep today"
          value={sleepTotalMin > 0 ? formatDuration(sleepTotalMin) : "0m"}
          detail={`${props.sleeps.length} nap${props.sleeps.length === 1 ? "" : "s"}`}
        />
      </div>
      <Stat
        label="Next appt"
        value={nextAppt ? format(parseISO(nextAppt.scheduled_at), "EEE") : "—"}
        detail={
          nextAppt
            ? format(parseISO(nextAppt.scheduled_at), "h:mm a")
            : "None scheduled"
        }
      />
    </section>
  );
}

function Stat(props: { label: string; value: string; detail: string }): JSX.Element {
  return (
    <div className="flex flex-col items-center px-1 text-center">
      <span className="text-[11px] uppercase tracking-wide text-slate-400">{props.label}</span>
      <span className="mt-1 text-base font-semibold text-slate-900">{props.value}</span>
      <span className="mt-0.5 text-xs text-slate-500 leading-tight">{props.detail}</span>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Quick log grid
// -----------------------------------------------------------------------------

interface QuickLogDef {
  key: string;
  label: string;
  icon: JSX.Element;
  bg: string;
  fg: string;
  message: string;
}

// `feed` is omitted from this list because the Feed tile navigates into the
// dedicated FeedHistoryPage instead of chatting with the agent.
const QUICK_LOGS: QuickLogDef[] = [
  {
    key: "sleep",
    label: "Sleep",
    icon: <MoonIcon className="h-5 w-5" />,
    bg: "bg-violet-100",
    fg: "text-violet-600",
    message: "Log a sleep / nap now.",
  },
  {
    key: "poop",
    label: "Poop",
    icon: <PoopIcon className="h-5 w-5" />,
    bg: "bg-amber-100",
    fg: "text-amber-700",
    message: "Log a poop now.",
  },
  {
    key: "appt",
    label: "Appt",
    icon: <StethoscopeIcon className="h-5 w-5" />,
    bg: "bg-pink-100",
    fg: "text-pink-600",
    message: "Add an appointment.",
  },
];

function QuickLogGrid(props: {
  onLog: (message: string) => void;
  onOpenChat: () => void;
  onOpenFeedHistory: () => void;
  disabled: boolean;
}): JSX.Element {
  return (
    <section aria-label="Quick log" className="flex flex-col gap-2">
      <h2 className="text-sm font-medium text-slate-700">Quick log</h2>
      <div className="grid grid-cols-4 gap-3">
        <QuickLogTile
          key="feed"
          label="Feed"
          icon={<DropIcon className="h-5 w-5" />}
          bg="bg-sky-100"
          fg="text-sky-600"
          disabled={false}
          onClick={props.onOpenFeedHistory}
        />
        {QUICK_LOGS.map((q) => (
          <QuickLogTile
            key={q.key}
            label={q.label}
            icon={q.icon}
            bg={q.bg}
            fg={q.fg}
            disabled={props.disabled}
            onClick={() => props.onLog(q.message)}
          />
        ))}
        <QuickLogTile
          key="more"
          label="More"
          icon={<PlusIcon className="h-5 w-5" />}
          bg="bg-slate-100"
          fg="text-slate-600"
          disabled={false}
          onClick={props.onOpenChat}
        />
      </div>
    </section>
  );
}

function QuickLogTile(props: {
  label: string;
  icon: JSX.Element;
  bg: string;
  fg: string;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={props.onClick}
      disabled={props.disabled}
      className="flex flex-col items-center gap-1.5 rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow disabled:opacity-50 disabled:hover:translate-y-0"
      aria-label={`Quick log ${props.label}`}
    >
      <span className={`grid h-10 w-10 place-items-center rounded-full ${props.bg} ${props.fg}`}>
        {props.icon}
      </span>
      <span className="text-xs font-medium text-slate-700">{props.label}</span>
    </button>
  );
}

// -----------------------------------------------------------------------------
// Recent logs
// -----------------------------------------------------------------------------

type LogItem = {
  id: string;
  iso: string;
  title: string;
  detail: string;
  bg: string;
  fg: string;
  icon: JSX.Element;
};

function RecentLogs(props: {
  feeds: FeedEntry[];
  sleeps: SleepEntry[];
  poops: PoopEntry[];
  appointments: AppointmentEntry[];
  loading: boolean;
}): JSX.Element {
  const items = useMemo<LogItem[]>(() => {
    const out: LogItem[] = [];
    for (const f of props.feeds) {
      out.push({
        id: `feed-${f.id}`,
        iso: f.occurred_at,
        title: f.feed_type === "formula" || f.feed_type === "breast_milk" ? "Bottle feed" : "Feed",
        detail: `${f.quantity}${f.unit} · ${shortFeed(f.feed_type)}`,
        bg: "bg-sky-100",
        fg: "text-sky-600",
        icon: <DropIcon className="h-4 w-4" />,
      });
    }
    for (const s of props.sleeps) {
      out.push({
        id: `sleep-${s.id}`,
        iso: s.start_at,
        title: "Sleep",
        detail: formatDuration(s.duration_minutes),
        bg: "bg-violet-100",
        fg: "text-violet-600",
        icon: <MoonIcon className="h-4 w-4" />,
      });
    }
    for (const p of props.poops) {
      out.push({
        id: `poop-${p.id}`,
        iso: p.occurred_at,
        title: "Poop",
        detail: p.consistency,
        bg: "bg-amber-100",
        fg: "text-amber-700",
        icon: <PoopIcon className="h-4 w-4" />,
      });
    }
    for (const a of props.appointments) {
      out.push({
        id: `appt-${a.id}`,
        iso: a.scheduled_at,
        title: "Appointment",
        detail: format(parseISO(a.scheduled_at), "h:mm a"),
        bg: "bg-pink-100",
        fg: "text-pink-600",
        icon: <StethoscopeIcon className="h-4 w-4" />,
      });
    }
    out.sort((a, b) => b.iso.localeCompare(a.iso));
    return out.slice(0, 6);
  }, [props.feeds, props.sleeps, props.poops, props.appointments]);

  return (
    <section aria-label="Recent logs" className="flex flex-col gap-2">
      <h2 className="text-sm font-medium text-slate-700">Recent logs</h2>
      {props.loading && items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white p-4 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
          No entries today yet — tap a quick-log tile above to add one.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((it) => (
            <li
              key={it.id}
              className="flex items-center gap-3 rounded-2xl bg-white px-3 py-2.5 shadow-sm ring-1 ring-slate-200"
            >
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${it.bg} ${it.fg}`}>
                {it.icon}
              </span>
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="text-sm font-medium text-slate-900">{it.title}</span>
                <span className="truncate text-xs text-slate-500">{it.detail}</span>
              </div>
              <span className="shrink-0 text-xs text-slate-400">
                {format(parseISO(it.iso), "HH:mm")}
              </span>
              <ChevronRightIcon className="h-4 w-4 shrink-0 text-slate-300" />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// -----------------------------------------------------------------------------
// Bottom tab bar (visual only — Home active; other tabs are placeholders)
// -----------------------------------------------------------------------------

function BottomTabBar(): JSX.Element {
  return (
    <nav
      aria-label="Primary"
      className="fixed bottom-3 left-1/2 z-10 flex w-[min(calc(100vw-1.5rem),22rem)] -translate-x-1/2 items-center justify-between rounded-full bg-white px-2 py-2 shadow-lg ring-1 ring-slate-200"
    >
      <TabButton label="Home" active icon={<HomeIcon className="h-5 w-5" />} />
      <TabButton label="Insights" icon={<ChartIcon className="h-5 w-5" />} />
      <TabButton label="Calendar" icon={<CalendarIcon className="h-5 w-5" />} />
      <TabButton label="Profile" icon={<UserIcon className="h-5 w-5" />} />
    </nav>
  );
}

function TabButton(props: { label: string; icon: JSX.Element; active?: boolean }): JSX.Element {
  const base =
    "flex flex-1 flex-col items-center gap-0.5 rounded-full py-1.5 text-[11px] font-medium transition";
  const active = "bg-amber-100 text-amber-700";
  const inactive = "text-slate-500 hover:text-slate-700";
  return (
    <button
      type="button"
      aria-current={props.active ? "page" : undefined}
      className={`${base} ${props.active ? active : inactive}`}
    >
      {props.icon}
      {props.label}
    </button>
  );
}

// -----------------------------------------------------------------------------
// Formatting helpers
// -----------------------------------------------------------------------------

function formatRelative(iso: string): string {
  try {
    return `${formatDistanceToNowStrict(parseISO(iso), { addSuffix: false })} ago`
      .replace("minutes", "min")
      .replace("minute", "min")
      .replace("hours", "h")
      .replace("hour", "h");
  } catch {
    return "—";
  }
}

function formatDuration(totalMin: number): string {
  if (totalMin <= 0) return "0m";
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

function shortFeed(t: string): string {
  switch (t) {
    case "breast_milk":
      return "breast";
    case "formula":
      return "formula";
    case "solids":
      return "solids";
    case "water":
      return "water";
    default:
      return t;
  }
}

// -----------------------------------------------------------------------------
// Inline SVG icons (no external icon dep)
// -----------------------------------------------------------------------------

type IconProps = { className?: string };

function SparkleIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2l1.8 4.6L18.4 8 13.8 9.8 12 14.4 10.2 9.8 5.6 8 10.2 6.6 12 2zm6 11l1 2.5L21.5 17 19 18l-1 2.5L17 18l-2.5-1L17 16l1-2.5z" />
    </svg>
  );
}

function BellIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8" />
      <path d="M10.3 21a2 2 0 003.4 0" />
    </svg>
  );
}

function DropIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2.5c2.5 3.5 7 8.2 7 12.3a7 7 0 11-14 0c0-4.1 4.5-8.8 7-12.3z" />
    </svg>
  );
}

function MoonIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M21 13.5A9 9 0 0110.5 3a7.5 7.5 0 1010.5 10.5z" />
    </svg>
  );
}

function PoopIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 3c0 2 2 3 2 5s-2 2-2 4c3 0 5 1.5 5 4 2 0 3 1.5 3 3.5S18.5 22 16 22H8c-2.5 0-4-1.5-4-3.5S5 15 7 15c0-2.5 2-4 5-4-2-1-3-2.5-3-4s2-2.5 3-4z" />
    </svg>
  );
}

function StethoscopeIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M6 3v6a4 4 0 008 0V3" />
      <path d="M10 13v3a4 4 0 008 0v-2" />
      <circle cx="18" cy="11" r="2" />
    </svg>
  );
}

function PlusIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className={className} aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function ChevronRightIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function HomeIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M3 11l9-7 9 7v9a2 2 0 01-2 2h-4v-6h-6v6H5a2 2 0 01-2-2v-9z" />
    </svg>
  );
}

function ChartIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </svg>
  );
}

function CalendarIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 10h18" />
    </svg>
  );
}

function UserIcon({ className }: IconProps): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0116 0" />
    </svg>
  );
}
