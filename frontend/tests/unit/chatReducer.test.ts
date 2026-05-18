import { describe, expect, it } from "vitest";
import { chatReducer } from "@/features/chat/reducer";
import { CHAT_HISTORY_LIMIT, INITIAL_CHAT, type ChatMessage } from "@/features/chat/types";

const caregiver = (text: string): ChatMessage => ({
  id: `c-${text}`,
  role: "caregiver",
  text,
  ts: 1,
});
const assistant = (text: string): ChatMessage => ({
  id: `a-${text}`,
  role: "assistant",
  text,
  ts: 2,
});

describe("chatReducer", () => {
  it("draft_changed updates draft", () => {
    const out = chatReducer(INITIAL_CHAT, { type: "draft_changed", value: "hello" });
    expect(out.draft).toBe("hello");
  });

  it("submit appends caregiver, sets inFlight true, clears draft", () => {
    const out = chatReducer(
      { ...INITIAL_CHAT, draft: "120 ml" },
      { type: "submit", userMessage: caregiver("120 ml") },
    );
    expect(out.inFlight).toBe(true);
    expect(out.draft).toBe("");
    expect(out.messages).toHaveLength(1);
    expect(out.messages[0]?.role).toBe("caregiver");
  });

  it("success appends assistant, clears inFlight", () => {
    const after = chatReducer(
      { messages: [caregiver("hi")], inFlight: true, draft: "" },
      { type: "success", assistantMessage: assistant("ok") },
    );
    expect(after.inFlight).toBe(false);
    expect(after.messages).toHaveLength(2);
  });

  it("error appends assistant, clears inFlight, preserves draft", () => {
    const after = chatReducer(
      { messages: [caregiver("hi")], inFlight: true, draft: "" },
      { type: "error", assistantMessage: assistant("oops"), preservedDraft: "hi" },
    );
    expect(after.inFlight).toBe(false);
    expect(after.draft).toBe("hi");
    expect(after.messages.at(-1)?.role).toBe("assistant");
  });

  it("FIFO-evicts at 100 messages", () => {
    let state = INITIAL_CHAT;
    for (let i = 0; i < CHAT_HISTORY_LIMIT + 5; i++) {
      state = chatReducer(state, { type: "submit", userMessage: caregiver(`m${i}`) });
      state = { ...state, inFlight: false };
    }
    expect(state.messages).toHaveLength(CHAT_HISTORY_LIMIT);
    expect(state.messages[0]?.text).toBe("m5"); // first 5 evicted
  });
});
