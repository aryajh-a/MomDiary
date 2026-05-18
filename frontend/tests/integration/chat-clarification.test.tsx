import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/features/chat/ChatPanel";
import clarification from "../fixtures/entries.clarification.json";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("ChatPanel — clarification", () => {
  it("renders the clarification question, no section invalidation, input retains focus", async () => {
    server.use(http.post(`${BASE}/v1/entries`, () => HttpResponse.json(clarification)));

    const { client } = renderWithProviders(<ChatPanel />);
    let invalidations = 0;
    const orig = client.invalidateQueries.bind(client);
    client.invalidateQueries = ((arg: unknown) => {
      invalidations++;
      return orig(arg as { queryKey: unknown[] });
    }) as typeof client.invalidateQueries;

    const input = screen.getByLabelText(/message/i);
    await userEvent.type(input, "I fed the baby");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText(/How much, and what type/)).toBeInTheDocument());
    expect(invalidations).toBe(0);
  });
});
