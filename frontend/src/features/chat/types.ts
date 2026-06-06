export type ChatRole = "caregiver" | "assistant";

export interface ChatMessageError {
  code: string;
  message: string;
}

export interface ChatMessageSource {
  title: string;
  url: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  ts: number;
  correlation_id?: string;
  error?: ChatMessageError;
  /**
   * Citations attached to a research assistant turn. `undefined` for
   * caregiver turns and for diary assistant turns; `[]` when the
   * research call returned no usable sources.
   */
  sources?: ChatMessageSource[];
}

export interface ChatSession {
  messages: ChatMessage[];
  inFlight: boolean;
  draft: string;
}

export type ChatAction =
  | { type: "draft_changed"; value: string }
  | { type: "submit"; userMessage: ChatMessage }
  | { type: "success"; assistantMessage: ChatMessage }
  | { type: "error"; assistantMessage: ChatMessage; preservedDraft: string };

export const CHAT_HISTORY_LIMIT = 100;

export const INITIAL_CHAT: ChatSession = {
  messages: [],
  inFlight: false,
  draft: "",
};
