import { createContext, useContext, type ReactNode } from "react";
import { useChat } from "./useChat";

type ChatApi = ReturnType<typeof useChat>;

const ChatContext = createContext<ChatApi | null>(null);

/**
 * Owns the singleton chat session for the home page. `ChatPanel` and quick-log
 * buttons both consume the same instance so a tap on a tile and a typed
 * message land in the same conversation thread (one `X-Session-ID`).
 */
export function ChatProvider({ children }: { children: ReactNode }): JSX.Element {
  const api = useChat();
  return <ChatContext.Provider value={api}>{children}</ChatContext.Provider>;
}

export function useChatContext(): ChatApi {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used inside <ChatProvider>");
  return ctx;
}
