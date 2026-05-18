import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { PoopsSection } from "@/features/poops/PoopsSection";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("PoopsSection", () => {
  it("renders consistency label", async () => {
    renderWithProviders(<PoopsSection />);
    await waitFor(() => expect(screen.getByText(/soft/i)).toBeInTheDocument());
  });
  it("renders the empty state", async () => {
    server.use(
      http.get(`${BASE}/v1/poops`, () => HttpResponse.json({ date: "2026-05-17", items: [] })),
    );
    renderWithProviders(<PoopsSection />);
    await screen.findByText(/no diaper/i);
  });
  it("renders error + retry on 500", async () => {
    server.use(http.get(`${BASE}/v1/poops`, () => HttpResponse.text("boom", { status: 500 })));
    renderWithProviders(<PoopsSection />);
    await screen.findByText(/something went wrong/i);
  });
});
