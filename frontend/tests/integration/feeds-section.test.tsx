import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { FeedsSection } from "@/features/feeds/FeedsSection";
import feeds from "../fixtures/feeds.list.json";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("FeedsSection", () => {
  it("renders fixture items in order with primary attribute prominent", async () => {
    renderWithProviders(<FeedsSection />);
    await waitFor(() => expect(screen.getByText(/120 ml/)).toBeInTheDocument());
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toMatch(/120 ml/);
    expect(items[1]?.textContent).toMatch(/90 ml/);
    // Primary attribute uses a large font class.
    expect(screen.getByText("120 ml").className).toMatch(/text-2xl/);
    void feeds;
  });

  it("renders the empty state when items is empty", async () => {
    server.use(
      http.get(`${BASE}/v1/feeds`, () => HttpResponse.json({ date: "2026-05-17", items: [] })),
    );
    renderWithProviders(<FeedsSection />);
    await screen.findByText(/no feeds logged/i);
  });

  it("renders the error state with retry button on 500", async () => {
    server.use(
      http.get(`${BASE}/v1/feeds`, () => HttpResponse.text("boom", { status: 500 })),
    );
    renderWithProviders(<FeedsSection />);
    await screen.findByText(/something went wrong/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
