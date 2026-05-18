import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { AppointmentsSection } from "@/features/appointments/AppointmentsSection";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("AppointmentsSection", () => {
  it("renders most-recent note preview and +N more indicator", async () => {
    renderWithProviders(<AppointmentsSection />);
    await waitFor(() => expect(screen.getByText(/Dr\. Lee/)).toBeInTheDocument());
    expect(screen.getByText(/\+1 more/)).toBeInTheDocument();
  });
  it("renders the empty state", async () => {
    server.use(
      http.get(`${BASE}/v1/appointments`, () =>
        HttpResponse.json({ date: "2026-05-17", items: [] }),
      ),
    );
    renderWithProviders(<AppointmentsSection />);
    await screen.findByText(/no appointments/i);
  });
  it("renders error + retry on 500", async () => {
    server.use(
      http.get(`${BASE}/v1/appointments`, () => HttpResponse.text("boom", { status: 500 })),
    );
    renderWithProviders(<AppointmentsSection />);
    await screen.findByText(/something went wrong/i);
  });
});
