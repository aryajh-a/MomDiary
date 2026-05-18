import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import App from "@/App";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("section isolation", () => {
  it("when feeds returns 500, other three sections still render", async () => {
    server.use(http.get(`${BASE}/v1/feeds`, () => HttpResponse.text("boom", { status: 500 })));
    renderWithProviders(<App />);

    await waitFor(() => {
      // Feeds region in error state
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });

    // Other sections still render their fixture content.
    await screen.findByText("1h 30m"); // sleeps
    await screen.findByText(/soft/i); // poops
    await screen.findByText(/Dr\. Lee/); // appointments
  });
});
