import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { SleepsSection } from "@/features/sleeps/SleepsSection";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("SleepsSection", () => {
  it("renders duration as '1h 30m'", async () => {
    renderWithProviders(<SleepsSection />);
    await waitFor(() => expect(screen.getByText("1h 30m")).toBeInTheDocument());
  });

  it("renders the empty state", async () => {
    server.use(
      http.get(`${BASE}/v1/sleeps`, () => HttpResponse.json({ date: "2026-05-17", items: [] })),
    );
    renderWithProviders(<SleepsSection />);
    await screen.findByText(/no sleeps/i);
  });

  it("renders error + retry on 500", async () => {
    server.use(
      http.get(`${BASE}/v1/sleeps`, () => HttpResponse.text("boom", { status: 500 })),
    );
    renderWithProviders(<SleepsSection />);
    await screen.findByText(/something went wrong/i);
  });
});
