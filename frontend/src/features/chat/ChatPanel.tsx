import { useCallback, useEffect, useRef, useState } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { useChat } from "./useChat";

interface ChatPanelProps {
  onHide?: () => void;
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
}

function useSpeechRecognition(opts: UseSpeechRecognitionOptions) {
  const { onTranscript, onFinal, lang } = opts;
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

  const Ctor = getSRCtor();
  const supported = Ctor !== null;

  const stop = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    try {
      rec.stop();
    } catch {
      // ignore
    }
  }, []);

  const start = useCallback(() => {
    if (!Ctor) return;
    if (recRef.current) {
      try {
        recRef.current.abort();
      } catch {
        // ignore
      }
    }
    let rec: SRInstance;
    try {
      rec = new Ctor();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Recognition unavailable");
      return;
    }
    rec.lang = lang ?? (typeof navigator !== "undefined" ? navigator.language : "en-US");
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (!r) continue;
        const t = r[0]?.transcript ?? "";
        if (r.isFinal) final += t;
        else interim += t;
      }
      const combined = (final + interim).trim();
      if (combined) onTranscriptRef.current(combined, !!final);
      if (final && onFinalRef.current) onFinalRef.current(final.trim());
    };
    rec.onerror = (e) => {
      setError(e.error || "Recognition error");
      setListening(false);
    };
    rec.onend = () => {
      setListening(false);
      recRef.current = null;
    };

    try {
      rec.start();
      recRef.current = rec;
      setError(null);
      setListening(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start mic");
    }
  }, [Ctor, lang]);

  const toggle = useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  useEffect(() => {
    return () => {
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

export function ChatPanel({ onHide }: ChatPanelProps = {}): JSX.Element {
  const { messages, inFlight, draft, setDraft, submit } = useChat();
  const [autoSend, setAutoSend] = useState(true);

  const onSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      void submit(draft);
    },
    [draft, submit],
  );

  const handleTranscript = useCallback(
    (text: string, _isFinal: boolean) => {
      setDraft(text);
    },
    [setDraft],
  );

  const handleFinal = useCallback(
    (text: string) => {
      if (autoSend && text.trim().length > 0) void submit(text);
    },
    [autoSend, submit],
  );

  const { supported, listening, error: micError, toggle, stop } =
    useSpeechRecognition({
      onTranscript: handleTranscript,
      onFinal: handleFinal,
    });

  // Stop the mic the moment a request goes out — avoids hot-mic loops and
  // is the right hook to also pause if you later add TTS for agent replies.
  useEffect(() => {
    if (inFlight && listening) stop();
  }, [inFlight, listening, stop]);

  return (
    <section
      aria-label="Chat"
      className="mx-auto flex w-full max-w-md flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-lg lg:max-w-none"
    >
      {onHide ? (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onHide}
            aria-label="Hide chat"
            className="rounded px-2 py-0.5 text-slate-500 text-xs hover:bg-slate-100 hover:text-slate-900"
          >
            ✕ Hide
          </button>
        </div>
      ) : null}
      <ChatMessageList messages={messages} />
      {inFlight ? (
        <p className="text-slate-500 text-xs" role="status" aria-live="polite">
          Thinking…
        </p>
      ) : null}
      {listening ? (
        <p className="text-rose-600 text-xs" role="status" aria-live="polite">
          🎙️ Listening…
        </p>
      ) : null}
      {micError ? (
        <p className="text-amber-700 text-xs" role="alert">
          Mic: {micError}
        </p>
      ) : null}
      <form onSubmit={onSubmit} className="flex items-end gap-2">
        <textarea
          aria-label="Message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          readOnly={inFlight}
          rows={2}
          placeholder="Log a feed, sleep, diaper, or appointment…"
          className="flex-1 resize-none rounded border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit(draft);
            }
          }}
        />
        {supported ? (
          <button
            type="button"
            onClick={toggle}
            disabled={inFlight}
            aria-pressed={listening}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            title={listening ? "Stop voice input" : "Start voice input"}
            className={
              "rounded px-3 py-2 text-sm transition-colors " +
              (listening
                ? "bg-rose-600 text-white hover:bg-rose-700"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200") +
              " disabled:opacity-50"
            }
          >
            {listening ? "● Stop" : "🎤"}
          </button>
        ) : null}
        <button
          type="submit"
          disabled={inFlight || draft.trim().length === 0}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:bg-slate-400"
        >
          Send
        </button>
      </form>
      {supported ? (
        <label className="flex items-center gap-2 text-slate-500 text-xs">
          <input
            type="checkbox"
            checked={autoSend}
            onChange={(e) => setAutoSend(e.target.checked)}
          />
          Auto-send after I stop speaking
        </label>
      ) : null}
    </section>
  );
}

export default ChatPanel;
