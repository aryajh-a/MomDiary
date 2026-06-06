import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { useChatContext } from "./ChatContext";
interface ChatPanelProps {
  onHide?: () => void;
  /**
   * When true the panel renders a voice-only experience: speech recognition
   * auto-starts on mount, there is no textarea, the mode switcher is hidden,
   * and every utterance is routed to the research API. Wired to the bottom
   * "Voice" tab.
   */
  voiceOnly?: boolean;
}

// -----------------------------------------------------------------------------
// Inline `useSpeechRecognition` — thin wrapper around the browser-native Web
// Speech API (Chrome / Edge / Safari). Firefox does not implement it; callers
// should gate UI on `supported`.
// -----------------------------------------------------------------------------

type SRResult = { isFinal: boolean; 0: { transcript: string } };
interface SRResultList {
  length: number;
  [index: number]: SRResult;
}
interface SREvent {
  resultIndex: number;
  results: SRResultList;
}
interface SRErrorEvent {
  error: string;
}
interface SRInstance {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: SRErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type SRConstructor = new () => SRInstance;

function getSRCtor(): SRConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SRConstructor;
    webkitSpeechRecognition?: SRConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

interface UseSpeechRecognitionOptions {
  onTranscript: (text: string, isFinal: boolean) => void;
  onFinal?: (text: string) => void;
  lang?: string;
  /**
   * How long the recognizer must hear silence (no new interim/final results)
   * before it commits and auto-submits. Users routinely pause mid-sentence,
   * so this should be generous — default 1800ms.
   */
  silenceMs?: number;
}

function useSpeechRecognition(opts: UseSpeechRecognitionOptions) {
  const { onTranscript, onFinal, lang, silenceMs = 1800 } = opts;
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SRInstance | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const onFinalRef = useRef(onFinal);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);
  useEffect(() => {
    onFinalRef.current = onFinal;
  }, [onFinal]);

  // Cross-restart session state. `start()` resets these; `onend` auto-restart
  // preserves them so the running transcript survives a browser-induced gap.
  const finalAccumRef = useRef("");
  const lastInterimRef = useRef("");
  const silenceTimerRef = useRef<number | null>(null);
  const manualStopRef = useRef(false);
  const committedRef = useRef(false);

  const Ctor = getSRCtor();
  const supported = Ctor !== null;

  const clearSilence = () => {
    if (silenceTimerRef.current != null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  // Fire the final transcript exactly once and stop the recognizer.
  const commit = useCallback(() => {
    if (committedRef.current) return;
    clearSilence();
    committedRef.current = true;
    manualStopRef.current = true;
    const text = (finalAccumRef.current + lastInterimRef.current).trim();
    const rec = recRef.current;
    if (rec) {
      try {
        rec.stop();
      } catch {
        // ignore
      }
    }
    if (text && onFinalRef.current) onFinalRef.current(text);
  }, []);

  // Cancel without submitting (user tapped the cancel pill).
  const stop = useCallback(() => {
    clearSilence();
    committedRef.current = true; // suppress any pending final
    manualStopRef.current = true;
    const rec = recRef.current;
    if (rec) {
      try {
        rec.stop();
      } catch {
        // ignore
      }
    }
  }, []);

  // Creates a fresh recognizer instance and wires its handlers. Used both for
  // a brand-new session (`start`) and to seamlessly resume after a browser
  // auto-end mid-utterance. Resetting of session state happens in `start()`.
  const createAndStart = useCallback(() => {
    if (!Ctor) return;
    let rec: SRInstance;
    try {
      rec = new Ctor();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Recognition unavailable");
      return;
    }
    rec.lang = lang ?? (typeof navigator !== "undefined" ? navigator.language : "en-US");
    rec.interimResults = true;
    // Continuous mode lets the user pause between words without the engine
    // finalising the utterance the moment they stop talking.
    rec.continuous = true;

    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (!r) continue;
        const t = r[0]?.transcript ?? "";
        if (r.isFinal) finalAccumRef.current += t;
        else interim += t;
      }
      lastInterimRef.current = interim;
      const combined = (finalAccumRef.current + interim).trim();
      if (combined) onTranscriptRef.current(combined, false);
      // Any speech activity resets the silence countdown.
      clearSilence();
      silenceTimerRef.current = window.setTimeout(() => {
        commit();
      }, silenceMs);
    };
    rec.onerror = (e) => {
      // "no-speech" is benign — the silence timer will eventually commit (or
      // the user will cancel). Surface anything else.
      if (e.error && e.error !== "no-speech" && e.error !== "aborted") {
        setError(e.error);
      }
    };
    rec.onend = () => {
      recRef.current = null;
      if (!manualStopRef.current && !committedRef.current) {
        // Browser auto-ended mid-session (Chrome does this even with
        // continuous=true after a few seconds of silence). Resume so the
        // user's pause doesn't terminate dictation.
        try {
          createAndStartRef.current();
          return;
        } catch {
          // fall through to a graceful close
        }
      }
      clearSilence();
      setListening(false);
      if (!committedRef.current) {
        committedRef.current = true;
        const text = (finalAccumRef.current + lastInterimRef.current).trim();
        if (text && onFinalRef.current) onFinalRef.current(text);
      }
    };

    try {
      rec.start();
      recRef.current = rec;
      setError(null);
      setListening(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start mic");
    }
  }, [Ctor, lang, silenceMs, commit]);

  const createAndStartRef = useRef(createAndStart);
  useEffect(() => {
    createAndStartRef.current = createAndStart;
  }, [createAndStart]);

  const start = useCallback(() => {
    if (!Ctor) return;
    // Fresh session — wipe accumulated transcript and flags.
    finalAccumRef.current = "";
    lastInterimRef.current = "";
    manualStopRef.current = false;
    committedRef.current = false;
    clearSilence();
    if (recRef.current) {
      try {
        recRef.current.abort();
      } catch {
        // ignore
      }
      recRef.current = null;
    }
    createAndStart();
  }, [Ctor, createAndStart]);

  const toggle = useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  useEffect(() => {
    return () => {
      clearSilence();
      const rec = recRef.current;
      if (rec) {
        try {
          rec.abort();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  return { supported, listening, error, start, stop, toggle };
}

// -----------------------------------------------------------------------------

export function ChatPanel({ onHide, voiceOnly = false }: ChatPanelProps = {}): JSX.Element {
  const { messages, inFlight, draft, setDraft, submit } = useChatContext();
  const autoSend = true;
  const [voiceMode, setVoiceMode] = useState(false);
  // Diary submissions go to /v1/entries (the existing agent dispatcher);
  // research submissions go to the placeholder /v1/research stub. See
  // `useChat.submit` for the routing.
  // Persist mode across panel mount/unmount. Both the Chat tab and the
  // Voice tab share the same mode setting — the caregiver can voice-log
  // ("Diary") or voice-ask research questions, and the UI's research
  // disclaimer + API endpoint pick up the choice in either tab.
  const [mode, setMode] = useState<ChatMode>(() => {
    if (typeof window === "undefined") return "diary";
    const stored = window.localStorage.getItem("momdiary.chatMode");
    return stored === "research" || stored === "diary" ? stored : "diary";
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("momdiary.chatMode", mode);
  }, [mode]);
  const modeCfg = MODE_CONFIG[mode];

  // Per-mode history isolation. The underlying chat store keeps a single
  // message stream (one session_id); we tag each message with the mode that
  // was active when its turn started, then filter at render time. The map
  // is a ref because the tagging is a write-once side-effect that must
  // not trigger re-renders.
  const messageModeRef = useRef<Map<string, ChatMode>>(new Map());
  // FIFO of modes for in-flight turns. `submitInMode` pushes the active mode
  // before dispatching `submit`; we shift one entry when the assistant reply
  // lands. This keeps a paired turn on the same mode even if the user
  // switches mid-request.
  const turnModeQueueRef = useRef<ChatMode[]>([]);

  // IMPORTANT: tagging must run during render (NOT in useEffect) so that
  // the filtered list below sees the freshly-arrived assistant message in
  // the SAME render that introduced it. If we deferred tagging to a
  // useEffect, the first render after a research reply would filter the
  // new assistant message out (its id wouldn't be in the map yet), and
  // it would only become visible on the next state change — i.e. when
  // the caregiver sends their next message. The `.has(id)` guard keeps
  // the mutation idempotent under React's render re-invocation.
  const { visibleMessages, inFlightHere } = useMemo(() => {
    for (const m of messages) {
      if (messageModeRef.current.has(m.id)) continue;
      if (m.role === "caregiver") {
        const next = turnModeQueueRef.current[0] ?? mode;
        messageModeRef.current.set(m.id, next);
      } else {
        const next = turnModeQueueRef.current.shift() ?? mode;
        messageModeRef.current.set(m.id, next);
      }
    }
    const visible = messages.filter(
      (m) => (messageModeRef.current.get(m.id) ?? "diary") === mode,
    );
    const typingHere =
      inFlight && (turnModeQueueRef.current[0] ?? mode) === mode;
    return { visibleMessages: visible, inFlightHere: typingHere };
  }, [messages, mode, inFlight]);

  const submitInMode = useCallback(
    (text: string) => {
      if (!text.trim() || inFlight) return;
      turnModeQueueRef.current.push(mode);
      void submit(text, mode);
    },
    [inFlight, mode, submit],
  );

  const onSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      submitInMode(draft);
    },
    [draft, submitInMode],
  );

  const handleTranscript = useCallback(
    (text: string, _isFinal: boolean) => {
      setDraft(text);
    },
    [setDraft],
  );

  const handleFinal = useCallback(
    (text: string) => {
      if (autoSend && text.trim().length > 0) submitInMode(text);
    },
    [autoSend, submitInMode],
  );

  const { listening, error: micError, start, stop } =
    useSpeechRecognition({
      onTranscript: handleTranscript,
      onFinal: handleFinal,
    });

  // Stop the mic the moment a request goes out — avoids hot-mic loops and
  // is the right hook to also pause if you later add TTS for agent replies.
  useEffect(() => {
    if (inFlight && listening) stop();
  }, [inFlight, listening, stop]);

  // When recognition ends (final transcript or stop()), close the voice view.
  // Guard with `hasListenedRef` so we don't immediately close in the gap
  // between `setVoiceMode(true)` and `setListening(true)` — or, importantly,
  // when `rec.start()` failed outright (e.g. permission denied) and listening
  // never flipped on. In that case we leave the overlay open so the user can
  // see the error message inside it and cancel manually.
  const hasListenedRef = useRef(false);
  useEffect(() => {
    if (listening) hasListenedRef.current = true;
  }, [listening]);
  useEffect(() => {
    if (voiceMode && !listening && hasListenedRef.current) {
      const t = setTimeout(() => {
        setVoiceMode(false);
        hasListenedRef.current = false;
      }, 250);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [voiceMode, listening]);

  const enterVoiceMode = useCallback(() => {
    if (inFlight) return;
    setDraft("");
    setVoiceMode(true);
    start();
  }, [inFlight, setDraft, start]);

  // Auto-start voice when the panel was opened via the bottom "Voice" tab.
  // Runs once on mount; if the browser doesn't support speech recognition
  // the call is a harmless no-op (the overlay simply shows the unsupported
  // state and the user can switch to typing).
  const didAutoStartVoiceRef = useRef(false);
  useEffect(() => {
    if (didAutoStartVoiceRef.current) return;
    if (!voiceOnly) return;
    didAutoStartVoiceRef.current = true;
    enterVoiceMode();
  }, [voiceOnly, enterVoiceMode]);

  const cancelVoiceMode = useCallback(() => {
    stop();
    setDraft("");
    setVoiceMode(false);
  }, [stop, setDraft]);

  const sendQuick = useCallback(
    (text: string) => {
      submitInMode(text);
    },
    [submitInMode],
  );

  return (
    <section
      aria-label="Chat"
      className="mx-auto flex h-[34rem] max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-orange-50 shadow-2xl ring-1 ring-orange-200 sm:rounded-2xl"
    >
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-orange-100 bg-orange-50 px-3 py-3">
        {onHide ? (
          <button
            type="button"
            onClick={onHide}
            aria-label="Close chat"
            className="grid h-8 w-8 place-items-center rounded-full text-orange-700 hover:bg-orange-100"
          >
            <BackIcon className="h-5 w-5" />
          </button>
        ) : null}
        <span className="grid h-9 w-9 place-items-center rounded-full bg-orange-100 ring-1 ring-orange-200">
          <SparkleIcon className="h-5 w-5 text-orange-600" />
        </span>
        <div className="flex flex-1 flex-col leading-tight">
          <span className="font-semibold text-slate-900 text-sm">Baby AI</span>
          <span className="text-[11px] text-slate-500">
            {voiceMode || listening ? (
              <span className="text-emerald-600">Listening…</span>
            ) : (
              <>
                <span className="text-emerald-600">● Online</span>
                <span className="px-1 text-slate-300">·</span>
                {modeCfg.subtitle}
              </>
            )}
          </span>
        </div>
      </header>

      {/* Mode switcher — visible in both Chat and Voice tabs so the
          caregiver can pick Diary vs Research either way. */}
      <div className="flex gap-1.5 border-b border-orange-100 bg-orange-50 px-3 py-2">
        {(Object.keys(MODE_CONFIG) as ChatMode[]).map((m) => {
          const cfg = MODE_CONFIG[m];
          const active = mode === m;
          return (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              aria-pressed={active}
              className={
                "flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium transition-colors " +
                (active
                  ? "bg-orange-500 text-white shadow-sm"
                  : "border border-orange-200 bg-white text-orange-700 hover:bg-orange-100")
              }
            >
              <cfg.Icon className="h-3.5 w-3.5" />
              {cfg.label}
            </button>
          );
        })}
      </div>

      {voiceOnly ? (
        <>
          {/* Voice-only experience: history above, voice control below. No
              textarea — every utterance is routed through the currently
              selected mode (Diary → /v1/entries, Research → /v1/research). */}
          <ChatMessageList messages={visibleMessages} inFlight={inFlightHere} />

          {micError ? (
            <div className="border-orange-100 border-t bg-orange-50 px-3 py-1">
              <p className="text-[11px] text-amber-700" role="alert">
                Mic: {micError}
              </p>
            </div>
          ) : null}

          {mode === "research" ? (
            <div className="flex items-start gap-2 border-orange-100 border-t bg-amber-50 px-3 py-1.5">
              <InfoIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              <p className="text-[11px] text-amber-800">
                General info from the web — not medical advice.
              </p>
            </div>
          ) : null}

          <VoiceControlBar
            voiceMode={voiceMode}
            listening={listening}
            transcript={draft}
            inFlight={inFlight}
            onStart={enterVoiceMode}
            onCancel={cancelVoiceMode}
          />
        </>
      ) : voiceMode ? (
        <VoiceOverlay
          transcript={draft}
          listening={listening}
          error={micError}
          onCancel={cancelVoiceMode}
          caption={modeCfg.voiceCaption}
        />
      ) : (
        <>
          {/* Scrollable messages */}
          <ChatMessageList messages={visibleMessages} inFlight={inFlightHere} />

          {/* Quick reply chips */}
          <div className="flex flex-wrap gap-2 border-orange-100 border-t bg-orange-50 px-3 py-2">
            {modeCfg.chips.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => sendQuick(q)}
                disabled={inFlight}
                className="rounded-full border border-orange-200 bg-white px-3 py-1 text-[12px] text-orange-700 hover:bg-orange-100 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Research disclaimer */}
          {mode === "research" ? (
            <div className="flex items-start gap-2 border-orange-100 border-t bg-amber-50 px-3 py-1.5">
              <InfoIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
              <p className="text-[11px] text-amber-800">
                General info from the web — not medical advice.
              </p>
            </div>
          ) : null}

          {/* Text composer — Chat tab is type-only; voice has its own tab. */}
          <form
            onSubmit={onSubmit}
            className="flex items-center gap-2 border-orange-100 border-t bg-orange-50 px-3 py-3"
          >
            <textarea
              aria-label="Message"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              readOnly={inFlight}
              rows={1}
              placeholder={modeCfg.placeholder}
              className="flex-1 resize-none rounded-full border border-orange-200 bg-white px-4 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-300"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitInMode(draft);
                }
              }}
            />
            <button
              type="submit"
              disabled={inFlight || draft.trim().length === 0}
              aria-label="Send"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-orange-500 text-white hover:bg-orange-600 disabled:bg-orange-300"
            >
              <SendIcon className="h-5 w-5" />
            </button>
          </form>
        </>
      )}
    </section>
  );
}

function VoiceOverlay({
  transcript,
  listening,
  error,
  onCancel,
  caption,
}: {
  transcript: string;
  listening: boolean;
  error: string | null;
  onCancel: () => void;
  caption: string;
}): JSX.Element {
  return (
    <div className="flex flex-1 flex-col items-center justify-between bg-orange-50 px-6 py-6">
      <p className="text-sm text-slate-500">{caption}</p>

      {/* Pulsing mic */}
      <div className="relative grid h-40 w-40 place-items-center">
        <span
          aria-hidden="true"
          className="absolute inline-flex h-full w-full rounded-full bg-orange-300/30 motion-safe:animate-ping"
        />
        <span
          aria-hidden="true"
          className="absolute inline-flex h-28 w-28 rounded-full bg-orange-300/40 motion-safe:animate-ping [animation-delay:-0.4s]"
        />
        <span
          aria-hidden="true"
          className="absolute inline-flex h-20 w-20 rounded-full bg-orange-200/60"
        />
        <span className="relative grid h-20 w-20 place-items-center rounded-full bg-orange-600 text-white shadow-lg">
          <MicIcon className="h-9 w-9" />
        </span>
      </div>

      {/* Waveform bars */}
      <div className="flex h-10 items-end gap-1" aria-hidden="true">
        {WAVEFORM_BARS.map((b, i) => (
          <span
            key={i}
            className={
              "w-1.5 rounded-full bg-orange-500 " +
              b.h +
              (listening ? " motion-safe:animate-pulse" : " opacity-40")
            }
            style={{ animationDelay: b.d }}
          />
        ))}
      </div>

      {/* Transcript card */}
      <div className="w-full rounded-2xl bg-orange-100/70 px-4 py-3 text-center ring-1 ring-orange-200">
        <p className="text-[11px] font-medium text-orange-700">
          {error ? "Mic error" : "Hearing…"}
        </p>
        <p className="mt-1 text-sm text-slate-800">
          {error ? error : transcript ? `“${transcript}”` : "…"}
        </p>
      </div>

      <button
        type="button"
        onClick={onCancel}
        className="rounded-full bg-white px-5 py-2 text-sm font-medium text-orange-700 shadow ring-1 ring-orange-200 hover:bg-orange-100"
      >
        Tap to cancel
      </button>
    </div>
  );
}

// Compact bottom voice control used in the voice-only experience. Shows a
// listening pill while the mic is active and a big "Tap to talk" mic button
// otherwise. Lets the message history above stay visible at all times.
function VoiceControlBar({
  voiceMode,
  listening,
  transcript,
  inFlight,
  onStart,
  onCancel,
}: {
  voiceMode: boolean;
  listening: boolean;
  transcript: string;
  inFlight: boolean;
  onStart: () => void;
  onCancel: () => void;
}): JSX.Element {
  const isListening = voiceMode || listening;
  if (isListening) {
    return (
      <div className="flex flex-col items-center gap-2 border-orange-100 border-t bg-orange-50 px-3 py-4">
        <div className="flex items-center gap-2">
          <span className="relative grid h-12 w-12 place-items-center rounded-full bg-orange-600 text-white shadow">
            <span
              aria-hidden="true"
              className="absolute inline-flex h-full w-full rounded-full bg-orange-300/50 motion-safe:animate-ping"
            />
            <MicIcon className="relative h-5 w-5" />
          </span>
          <span className="text-[11px] font-medium text-orange-700">Listening…</span>
        </div>
        {transcript ? (
          <p className="line-clamp-2 max-w-[260px] text-center text-[12px] text-slate-700">
            “{transcript}”
          </p>
        ) : null}
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full bg-white px-4 py-1.5 text-[12px] font-medium text-orange-700 ring-1 ring-orange-200 hover:bg-orange-100"
        >
          Tap to cancel
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-1.5 border-orange-100 border-t bg-orange-50 px-3 py-4">
      <button
        type="button"
        onClick={onStart}
        disabled={inFlight}
        aria-label="Tap to talk"
        className="grid h-16 w-16 place-items-center rounded-full bg-orange-500 text-white shadow-lg transition-colors hover:bg-orange-600 disabled:bg-orange-300"
      >
        <MicIcon className="h-7 w-7" />
      </button>
      <span className="text-[11px] text-slate-600">
        {inFlight ? "Thinking…" : "Tap to talk"}
      </span>
    </div>
  );
}

const WAVEFORM_BARS: ReadonlyArray<{ h: string; d: string }> = [
  { h: "h-2", d: "0s" },
  { h: "h-4", d: "-0.15s" },
  { h: "h-6", d: "-0.3s" },
  { h: "h-8", d: "-0.45s" },
  { h: "h-10", d: "-0.6s" },
  { h: "h-8", d: "-0.75s" },
  { h: "h-6", d: "-0.9s" },
  { h: "h-4", d: "-1.05s" },
  { h: "h-3", d: "-1.2s" },
  { h: "h-5", d: "-1.35s" },
  { h: "h-7", d: "-1.5s" },
  { h: "h-3", d: "-1.65s" },
];

type ChatMode = "diary" | "research";

interface ModeConfig {
  label: string;
  subtitle: string;
  placeholder: string;
  voiceCaption: string;
  chips: readonly string[];
  Icon: (props: { className?: string }) => JSX.Element;
}

const MODE_CONFIG: Record<ChatMode, ModeConfig> = {
  diary: {
    label: "Diary",
    subtitle: "Baby's diary assistant",
    placeholder: "Log or ask about your baby…",
    voiceCaption: "Speak about your baby…",
    chips: ["Log a nap", "Just fed 5 min", "Last feed?", "How did she sleep?"],
    Icon: SparkleIcon,
  },
  research: {
    label: "Research",
    subtitle: "Web research",
    placeholder: "Search the web about babies…",
    voiceCaption: "Researching the web…",
    chips: [
      "Safe sleep at 4 mo",
      "Teething tips",
      "Tummy time ideas",
      "Starting solids",
    ],
    Icon: GlobeIcon,
  },
};

function BackIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

function SparkleIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2l1.7 4.3L18 8l-4.3 1.7L12 14l-1.7-4.3L6 8l4.3-1.7L12 2z" />
      <path d="M19 14l.8 1.9L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-1.1L19 14z" />
    </svg>
  );
}

function MicIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" stroke="none" />
      <path d="M5 11a7 7 0 0014 0" />
      <path d="M12 18v3" />
    </svg>
  );
}

function SendIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M3 20l18-8L3 4l3 8-3 8z" />
    </svg>
  );
}

function GlobeIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 010 18" />
      <path d="M12 3a14 14 0 000 18" />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8h.01" />
      <path d="M11 12h1v5h1" />
    </svg>
  );
}

export default ChatPanel;
