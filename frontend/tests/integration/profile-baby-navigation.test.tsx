/**
 * Profile → Baby Profile navigation + cross-baby isolation (Feature 010, FR-007).
 *
 * Tapping a baby on the Profile list opens that baby's detail screen; opening
 * baby A, returning, then opening baby B shows only B's data — no carryover.
 */
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfilePage } from "@/features/profile";
import type { Baby, UserPublic } from "@/shared/types";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

const USER: UserPublic = {
  id: 1,
  email: "mom@example.com",
  display_name: "Mom Example",
  email_verified: true,
  active_baby_id: 10,
};

function baby(over: Partial<Baby>): Baby {
  return {
    id: 10,
    owner_user_id: 1,
    display_name: "Liam",
    date_of_birth: "2024-03-01",
    color_tag: null,
    gender: null,
    weight_kg: null,
    height_cm: null,
    last_measured_at: null,
    weight_kg_delta: null,
    height_cm_delta: null,
    created_at: "2024-03-01T00:00:00+00:00",
    updated_at: "2024-03-01T00:00:00+00:00",
    ...over,
  };
}

const BABY_A = baby({ id: 10, display_name: "Liam", gender: "boy", weight_kg: 9 });
const BABY_B = baby({ id: 11, display_name: "Mia", gender: "girl", weight_kg: 7 });

describe("ProfilePage → BabyProfilePage navigation", () => {
  it("opens the tapped baby, and switching babies shows only that baby's data", async () => {
    server.use(
      http.get(`${BASE}/v1/babies`, () =>
        HttpResponse.json({ items: [BABY_A, BABY_B] }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);

    // Open baby A.
    const cardA = await screen.findByLabelText("Baby Liam");
    await user.click(within(cardA).getByRole("button", { name: /open liam's profile/i }));

    let details = await screen.findByRole("region", { name: /baby details/i });
    let growth = screen.getByRole("region", { name: /growth measurements/i });
    expect(
      screen.getByRole("heading", { name: "Liam", level: 2 }),
    ).toBeInTheDocument();
    expect(within(details).getByText("Boy")).toBeInTheDocument();
    expect(within(growth).getByText("9 kg")).toBeInTheDocument();
    expect(within(details).queryByText("Girl")).not.toBeInTheDocument();

    // Back to the list, then open baby B.
    await user.click(screen.getByRole("button", { name: /back to profile/i }));
    const cardB = await screen.findByLabelText("Baby Mia");
    await user.click(within(cardB).getByRole("button", { name: /open mia's profile/i }));

    details = await screen.findByRole("region", { name: /baby details/i });
    growth = screen.getByRole("region", { name: /growth measurements/i });
    expect(
      screen.getByRole("heading", { name: "Mia", level: 2 }),
    ).toBeInTheDocument();
    expect(within(details).getByText("Girl")).toBeInTheDocument();
    expect(within(growth).getByText("7 kg")).toBeInTheDocument();
    // No bleed-through from baby A.
    expect(within(details).queryByText("Boy")).not.toBeInTheDocument();
    expect(within(growth).queryByText("9 kg")).not.toBeInTheDocument();
  });
});
