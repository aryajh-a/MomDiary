import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useReducer } from "react";
import { ApiError, apiClient } from "@/shared/apiClient";
import { entryTypeToSection } from "@/shared/queryKeys";
import type { AgentWriteResponse } from "@/shared/types";
import { chatReducer } from "./reducer";
import { INITIAL_CHAT, type ChatMessage } from "./types";

function makeId(): string {
  const g = globalThis.crypto;
  if (g && typeof g.randomUUID === "function") return g.randomUUID();
  return `m-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, INITIAL_CHAT);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (message: string) => apiClient.postEntry({ message }),
  });

  const setDraft = useCallback((value: string) => {
    dispatch({ type: "draft_changed", value });
  }, []);

  const submit = useCallback(
    async (rawDraft: string) => {
      const draft = rawDraft.trim();
      if (!draft || state.inFlight) return;

      const userMessage: ChatMessage = {
        id: makeId(),
        role: "caregiver",
        text: draft,
        ts: Date.now(),
      };
      dispatch({ type: "submit", userMessage });

      try {
        const response: AgentWriteResponse = await mutation.mutateAsync(draft);
        const assistantMessage: ChatMessage = {
          id: makeId(),
          role: "assistant",
          text: response.agent_message,
          ts: Date.now(),
          correlation_id: response.correlation_id,
        };
        dispatch({ type: "success", assistantMessage });

        if (
          response.outcome === "created" ||
          response.outcome === "updated" ||
          response.outcome === "deleted"
        ) {
          const section = entryTypeToSection[response.entry_type];
          if (section) {
            // Invalidate every cached date for this section: the entry's
            // `occurred_at` may land on a different day than the currently
            // selected one, so a date-scoped invalidation can silently miss.
            await qc.invalidateQueries({ queryKey: [section] });
          }
        }
      } catch (cause) {
        const apiErr = cause instanceof ApiError ? cause : null;
        const assistantMessage: ChatMessage = {
          id: makeId(),
          role: "assistant",
          text:
            "Something went wrong saving that — please try again. If it keeps happening, share the correlation ID below.",
          ts: Date.now(),
          correlation_id: apiErr?.correlationId,
          error: {
            code: apiErr?.code ?? "unknown_error",
            message: apiErr?.message ?? (cause instanceof Error ? cause.message : "Unknown error"),
          },
        };
        dispatch({ type: "error", assistantMessage, preservedDraft: draft });
      }
    },
    [state.inFlight, mutation, qc],
  );

  return {
    messages: state.messages,
    inFlight: state.inFlight,
    draft: state.draft,
    setDraft,
    submit,
  };
}
