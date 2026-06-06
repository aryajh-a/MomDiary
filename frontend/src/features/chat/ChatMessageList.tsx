import { useEffect, useRef } from "react";
import { format } from "date-fns";
import { AssistantMessageBody } from "./AssistantMessageBody";
import type { ChatMessage } from "./types";

interface Props {
  messages: ChatMessage[];
  inFlight: boolean;
}

export function ChatMessageList({ messages, inFlight }: Props): JSX.Element {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = endRef.current;
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end" });
    }
  }, [messages.length, inFlight]);

  return (
    <ul
      className="flex flex-1 flex-col gap-3 overflow-y-auto bg-orange-50/60 px-3 py-3"
      aria-label="Chat history"
    >
      {messages.map((m) =>
        m.role === "assistant" ? (
          <AssistantRow key={m.id} message={m} />
        ) : (
          <CaregiverRow key={m.id} message={m} />
        ),
      )}
      {inFlight ? <TypingRow /> : null}
      <div ref={endRef} />
    </ul>
  );
}

function AssistantRow({ message }: { message: ChatMessage }): JSX.Element {
  const isResearch =
    (message.sources !== undefined && message.sources.length > 0) ||
    /This is general information, not medical advice/.test(message.text);
  // Research replies get the structured renderer (paragraphs, lists,
  // bold, sources, disclaimer). Diary replies stay on the simple
  // single-paragraph path — they're already terse confirmations like
  // "Logged 120 ml of breast milk." and don't benefit from formatting.
  return (
    <li className="flex items-end gap-2">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-orange-100 ring-1 ring-orange-200">
        <SparkleIcon className="h-4 w-4 text-orange-600" />
      </span>
      <div
        className={
          isResearch
            ? "flex max-w-[92%] flex-col items-start"
            : "flex max-w-[78%] flex-col items-start"
        }
      >
        <div
          className={
            message.error
              ? "rounded-2xl rounded-bl-md bg-red-50 px-3 py-2 text-red-900 text-sm shadow-sm ring-1 ring-red-200"
              : "rounded-2xl rounded-bl-md bg-white px-3 py-2 text-slate-800 text-sm shadow-sm ring-1 ring-orange-100"
          }
        >
          {isResearch && !message.error ? (
            <AssistantMessageBody text={message.text} sources={message.sources} />
          ) : (
            <p className="whitespace-pre-wrap leading-snug">{message.text}</p>
          )}
          {message.error ? (
            <p className="mt-1 text-red-700 text-xs">
              {message.error.code}: {message.error.message}
            </p>
          ) : null}
        </div>
        <time className="mt-1 px-1 text-[10px] text-slate-400">
          {format(new Date(message.ts), "h:mm a")}
        </time>
      </div>
    </li>
  );
}

function CaregiverRow({ message }: { message: ChatMessage }): JSX.Element {
  return (
    <li className="flex flex-col items-end">
      <div className="max-w-[78%] rounded-2xl rounded-br-md bg-orange-500 px-3 py-2 text-sm text-white shadow-sm">
        <p className="whitespace-pre-wrap leading-snug">{message.text}</p>
      </div>
      <time className="mt-1 px-1 text-[10px] text-slate-400">
        {format(new Date(message.ts), "h:mm a")}
      </time>
    </li>
  );
}

function TypingRow(): JSX.Element {
  return (
    <li className="flex items-end gap-2" role="status" aria-live="polite">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-orange-100 ring-1 ring-orange-200">
        <SparkleIcon className="h-4 w-4 text-orange-600" />
      </span>
      <div className="rounded-2xl rounded-bl-md bg-white px-3 py-2 text-slate-500 text-sm shadow-sm ring-1 ring-orange-100">
        <span className="inline-flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-orange-400 [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-orange-400 [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-orange-400" />
        </span>
      </div>
    </li>
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
