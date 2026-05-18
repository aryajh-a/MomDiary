import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { FeedsSection } from "@/features/feeds/FeedsSection";
import created from "../fixtures/entries.created.json";
import emptyFeeds from "../fixtures/feeds.list.json";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("Chat → feeds refresh", () => {
  it("invalidates the feeds query after a created envelope so new data appears", async () => {
    let call = 0;
    server.use(
      http.get(`${BASE}/v1/feeds`, () => {
        call++;
        if (call === 1) return HttpResponse.json({ date: "2026-05-17", items: [] });
        return HttpResponse.json(emptyFeeds);
      }),
      http.post(`${BASE}/v1/entries`, () => HttpResponse.json(created)),
    );

    renderWithProviders(
      <>
        <FeedsSection />
        <ChatPanel />
      </>,
    );

    await screen.findByText(/no feeds/i);

    await userEvent.type(screen.getByLabelText(/message/i), "120 ml breast milk");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText("120 ml")).toBeInTheDocument(), {
      timeout: 2000,
    });
  });
});
