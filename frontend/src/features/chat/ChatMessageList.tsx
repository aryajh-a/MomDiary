import { useEffect, useRef } from "react";
import type { ChatMessage } from "./types";

export function ChatMessageList({ messages }: { messages: ChatMessage[] }): JSX.Element {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = endRef.current;
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end" });
    }
  }, [messages.length]);

  return (
    <ul className="flex max-h-60 flex-col gap-2 overflow-y-auto" aria-label="Chat history">
      {messages.map((m) => (
        <li
          key={m.id}
          className={
            m.role === "caregiver"
              ? "self-end rounded-2xl bg-slate-200 px-3 py-2 text-sm"
              : m.error
                ? "self-start rounded-2xl bg-red-50 px-3 py-2 text-red-900 text-sm"
                : "self-start rounded-2xl bg-white px-3 py-2 text-sm shadow-sm"
          }
        >
          <p>{m.text}</p>
          {m.role === "assistant" && m.correlation_id ? (
            <details className="mt-1 text-slate-500 text-xs">
              <summary>Details</summary>
              <code className="font-mono">{m.correlation_id}</code>
              {m.error ? <p className="mt-1">{m.error.code}: {m.error.message}</p> : null}
            </details>
          ) : null}
        </li>
      ))}
      <div ref={endRef} />
    </ul>
  );
}
