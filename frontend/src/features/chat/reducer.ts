import { CHAT_HISTORY_LIMIT, type ChatAction, type ChatSession } from "./types";

function append(state: ChatSession, msg: ChatSession["messages"][number]): ChatSession["messages"] {
  const next = [...state.messages, msg];
  if (next.length > CHAT_HISTORY_LIMIT) {
    return next.slice(next.length - CHAT_HISTORY_LIMIT);
  }
  return next;
}

export function chatReducer(state: ChatSession, action: ChatAction): ChatSession {
  switch (action.type) {
    case "draft_changed":
      return { ...state, draft: action.value };
    case "submit":
      return {
        messages: append(state, action.userMessage),
        inFlight: true,
        draft: "",
      };
    case "success":
      return {
        messages: append(state, action.assistantMessage),
        inFlight: false,
        draft: "",
      };
    case "error":
      return {
        messages: append(state, action.assistantMessage),
        inFlight: false,
        draft: action.preservedDraft,
      };
    default: {
      action satisfies never;
      return state;
    }
  }
}
