import { useCallback } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { useChat } from "./useChat";

interface ChatPanelProps {
  onHide?: () => void;
}

export function ChatPanel({ onHide }: ChatPanelProps = {}): JSX.Element {
  const { messages, inFlight, draft, setDraft, submit } = useChat();

  const onSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      void submit(draft);
    },
    [draft, submit],
  );

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
        <button
          type="submit"
          disabled={inFlight || draft.trim().length === 0}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:bg-slate-400"
        >
          Send
        </button>
      </form>
    </section>
  );
}

export default ChatPanel;
