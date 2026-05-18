import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import App from "@/App";
import { renderWithProviders } from "../_msw/renderWithProviders";

describe("visual identity", () => {
  it("each section has region role + aria-label + icon with title + header label + large primary attribute", async () => {
    renderWithProviders(<App />);

    await waitFor(() => {
      // wait until at least one section has data
      expect(screen.getByText(/120 ml/)).toBeInTheDocument();
    });

    for (const label of ["Feeds", "Sleeps", "Poops", "Appointments"]) {
      const region = screen.getByRole("region", { name: label });
      expect(region).toBeInTheDocument();
      const icon = within(region).getByRole("img");
      expect(icon).toBeInTheDocument();
      expect(within(icon).getByText(/./)).toBeInTheDocument(); // <title> text
    }

    // Primary attributes carry the large-text class.
    expect(screen.getByText("120 ml").className).toMatch(/text-2xl/);
    expect(screen.getByText("1h 30m").className).toMatch(/text-2xl/);
    expect(screen.getByText(/^Soft$/).className).toMatch(/text-2xl/);
  });
});
