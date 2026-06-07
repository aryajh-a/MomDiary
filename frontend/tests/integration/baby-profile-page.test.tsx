/**
 * Baby Profile detail screen — integration tests (Feature 010).
 *
 * Covers US1 (read-only view with placeholders) and US2 (edit: pre-fill,
 * cancel, validation, clear-to-null, save round-trip) against the MSW-mocked
 * HTTP API. Pure formatting is unit-tested in babyProfileFormat.test.ts.
 */
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BabyProfilePage } from "@/features/profile";
import type { Baby } from "@/shared/types";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

function baby(over: Partial<Baby> = {}): Baby {
  return {
    id: 10,
    owner_user_id: 1,
    display_name: "Mia Johnson",
    date_of_birth: "2025-01-20",
    color_tag: null,
    gender: "girl",
    weight_kg: 7.2,
    height_cm: 62,
    last_measured_at: "2025-05-10",
    weight_kg_delta: 0.3,
    height_cm_delta: 1.5,
    created_at: "2025-01-20T00:00:00+00:00",
    updated_at: "2025-01-20T00:00:00+00:00",
    ...over,
  };
}

describe("BabyProfilePage — US1 view", () => {
  it("renders identity, details, and the growth card in metric units", () => {
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    expect(
      screen.getByRole("heading", { name: "Mia Johnson", level: 2 }),
    ).toBeInTheDocument();

    const details = screen.getByRole("region", { name: /baby details/i });
    expect(within(details).getByText("Girl")).toBeInTheDocument();

    const growth = screen.getByRole("region", { name: /growth measurements/i });
    expect(within(growth).getByText("7.2 kg")).toBeInTheDocument();
    expect(within(growth).getByText("62 cm")).toBeInTheDocument();
  });

  it("shows the growth delta (↑/↓) and last-measured date", () => {
    renderWithProviders(
      <BabyProfilePage
        baby={baby({ weight_kg_delta: 0.3, height_cm_delta: -0.5 })}
        onBack={() => {}}
      />,
    );
    const growth = screen.getByRole("region", { name: /growth measurements/i });
    expect(within(growth).getByText("↑0.3 kg")).toBeInTheDocument();
    expect(within(growth).getByText("↓0.5 cm")).toBeInTheDocument();
    // "Last measured" date is rendered (locale-formatted).
    expect(within(growth).getByText(/may/i)).toBeInTheDocument();
  });

  it("omits the delta badge when there is no prior measurement", () => {
    renderWithProviders(
      <BabyProfilePage
        baby={baby({ weight_kg_delta: null, height_cm_delta: null })}
        onBack={() => {}}
      />,
    );
    const growth = screen.getByRole("region", { name: /growth measurements/i });
    expect(within(growth).queryByText(/↑|↓/)).not.toBeInTheDocument();
  });

  it("shows an explicit 'Not set' placeholder for each unset optional field", () => {
    renderWithProviders(
      <BabyProfilePage
        baby={baby({
          gender: null,
          weight_kg: null,
          height_cm: null,
          last_measured_at: null,
        })}
        onBack={() => {}}
      />,
    );
    // Gender unset (details) + weight, height, last-measured unset (growth).
    expect(screen.getAllByText("Not set")).toHaveLength(4);
  });

  it("exposes an inert, accessibly-labelled photo affordance (FR-017)", () => {
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);
    const photo = screen.getByRole("button", { name: /add photo \(coming soon\)/i });
    expect(photo).toBeDisabled();
  });
});

describe("BabyProfilePage — US2 edit", () => {
  it("pre-fills the form, and Cancel restores view mode without calling the API", async () => {
    let calls = 0;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, () => {
        calls++;
        return HttpResponse.json(baby());
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit profile/i }));
    const form = screen.getByRole("form", { name: /edit baby profile/i });
    expect(within(form).getByDisplayValue("Mia Johnson")).toBeInTheDocument();
    expect(within(form).getByDisplayValue("7.2")).toBeInTheDocument();

    await user.click(within(form).getByRole("button", { name: /cancel/i }));
    expect(
      screen.queryByRole("form", { name: /edit baby profile/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit profile/i })).toBeInTheDocument();
    expect(calls).toBe(0);
  });

  it("PATCHes valid edits, then exits to view mode", async () => {
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(baby({ gender: "boy" }));
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit profile/i }));
    const form = screen.getByRole("form", { name: /edit baby profile/i });
    await user.selectOptions(within(form).getByLabelText(/gender/i), "boy");
    await user.click(within(form).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(patched).toMatchObject({ gender: "boy" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("form", { name: /edit baby profile/i }),
      ).not.toBeInTheDocument(),
    );
  });

  it("sends explicit null to clear an optional field (FR-014)", async () => {
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(baby({ weight_kg: null }));
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit profile/i }));
    const form = screen.getByRole("form", { name: /edit baby profile/i });
    await user.clear(within(form).getByLabelText(/weight/i));
    await user.click(within(form).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched).toMatchObject({ weight_kg: null });
  });

  it("blocks a non-positive weight with an inline error and never calls the API", async () => {
    let calls = 0;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, () => {
        calls++;
        return HttpResponse.json(baby());
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit profile/i }));
    const form = screen.getByRole("form", { name: /edit baby profile/i });
    const weight = within(form).getByLabelText(/weight/i);
    await user.clear(weight);
    await user.type(weight, "0");
    await user.click(within(form).getByRole("button", { name: /save/i }));

    expect(await within(form).findByRole("alert")).toHaveTextContent(/positive/i);
    expect(calls).toBe(0);
  });

  it("blocks a future date of birth client-side", async () => {
    let calls = 0;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, () => {
        calls++;
        return HttpResponse.json(baby());
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<BabyProfilePage baby={baby()} onBack={() => {}} />);

    await user.click(screen.getByRole("button", { name: /edit profile/i }));
    const form = screen.getByRole("form", { name: /edit baby profile/i });
    const dob = within(form).getByLabelText(/date of birth/i);
    await user.clear(dob);
    await user.type(dob, "2999-01-01");
    await user.click(within(form).getByRole("button", { name: /save/i }));

    expect(await within(form).findByRole("alert")).toHaveTextContent(/future/i);
    expect(calls).toBe(0);
  });
});
