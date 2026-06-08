/**
 * Profile surface — integration tests (Feature 007).
 *
 * Covers the user-visible flows for US1–US5 against the MSW-mocked HTTP API.
 * Heavy edge-case validation (whitespace 422, age display, etc.) is left to
 * focused unit tests; this file exercises the orchestration: page wiring,
 * edit/save round-trip, remove confirmation, add-baby modal.
 */
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
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

function baby(over: Partial<Baby> = {}): Baby {
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

function withDefaults(babies: Baby[]) {
  server.use(
    http.get(`${BASE}/v1/babies`, () => HttpResponse.json({ items: babies })),
  );
}

describe("ProfilePage — US1 view", () => {
  it("shows caregiver details and one card per non-deleted baby with an active badge", async () => {
    withDefaults([
      baby(),
      baby({ id: 11, display_name: "Mia", date_of_birth: "2022-05-15" }),
    ]);
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);

    expect(await screen.findByRole("heading", { name: /profile/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByText(USER.display_name)).toBeInTheDocument();
    expect(screen.getByText(USER.email)).toBeInTheDocument();

    const liam = await screen.findByLabelText("Baby Liam");
    expect(within(liam).getByText("Active")).toBeInTheDocument();

    const mia = screen.getByLabelText("Baby Mia");
    expect(within(mia).queryByText("Active")).not.toBeInTheDocument();
  });

  it("renders an empty state with an Add a baby call to action", async () => {
    withDefaults([]);
    renderWithProviders(
      <ProfilePage user={{ ...USER, active_baby_id: null as unknown as number }} onBack={() => {}} />,
    );
    expect(await screen.findByText(/no babies yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add a baby/i })).toBeInTheDocument();
  });
});

describe("ProfilePage — US2 edit caregiver", () => {
  it("saves a new display name and exits edit mode", async () => {
    withDefaults([baby()]);
    let patched: { display_name?: string } | null = null;
    server.use(
      http.patch(`${BASE}/v1/users/me`, async ({ request }) => {
        patched = (await request.json()) as { display_name?: string };
        return HttpResponse.json({
          user: { ...USER, display_name: patched?.display_name ?? USER.display_name },
        });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    await screen.findByText("Liam");

    const section = screen.getByRole("region", { name: /your details/i });
    await user.click(within(section).getByRole("button", { name: /edit/i }));
    const input = within(section).getByDisplayValue(USER.display_name);
    await user.clear(input);
    await user.type(input, "Renamed Mom");
    await user.click(within(section).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(patched).toEqual({ display_name: "Renamed Mom" }));
    await waitFor(() =>
      expect(within(section).queryByRole("button", { name: /save/i })).not.toBeInTheDocument(),
    );
  });

  it("blocks an empty display name with an inline error and never calls the API", async () => {
    withDefaults([baby()]);
    let calls = 0;
    server.use(
      http.patch(`${BASE}/v1/users/me`, () => {
        calls++;
        return HttpResponse.json({ user: USER });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    await screen.findByText("Liam");
    const section = screen.getByRole("region", { name: /your details/i });
    await user.click(within(section).getByRole("button", { name: /edit/i }));
    const input = within(section).getByDisplayValue(USER.display_name);
    await user.clear(input);
    await user.type(input, "   ");
    await user.click(within(section).getByRole("button", { name: /save/i }));

    expect(await within(section).findByRole("alert")).toHaveTextContent(/can't be empty/i);
    expect(calls).toBe(0);
  });
});

describe("ProfilePage — US3 edit baby", () => {
  it("PATCHes display name + date of birth and exits edit mode", async () => {
    withDefaults([baby()]);
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.patch(`${BASE}/v1/babies/10`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          baby({ display_name: String(patched?.display_name ?? "Liam"), date_of_birth: String(patched?.date_of_birth ?? "2024-03-01") }),
        );
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    // Editing now lives inside the baby profile sheet — open it first.
    const card = await screen.findByLabelText("Baby Liam");
    await user.click(within(card).getByRole("button", { name: /open liam's profile/i }));
    await user.click(screen.getByRole("button", { name: /edit profile/i }));

    const form = screen.getByRole("form", { name: /edit baby profile/i });
    const name = within(form).getByDisplayValue("Liam");
    await user.clear(name);
    await user.type(name, "Liam Jr");
    await user.click(within(form).getByRole("button", { name: /save/i }));

    await waitFor(() => expect(patched).toMatchObject({ display_name: "Liam Jr", date_of_birth: "2024-03-01" }));
  });

  it("rejects a future date of birth client-side", async () => {
    withDefaults([baby()]);
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    const card = await screen.findByLabelText("Baby Liam");
    await user.click(within(card).getByRole("button", { name: /open liam's profile/i }));
    await user.click(screen.getByRole("button", { name: /edit profile/i }));

    const form = screen.getByRole("form", { name: /edit baby profile/i });
    const dob = within(form).getByDisplayValue("2024-03-01");
    // jsdom may not respect <input type="date" max>; assert via the input value
    // we set and the resulting error path.
    await user.clear(dob);
    await user.type(dob, "2999-01-01");
    await user.click(within(form).getByRole("button", { name: /save/i }));
    expect(await within(form).findByRole("alert")).toHaveTextContent(/future/i);
  });
});

describe("ProfilePage — US4 remove baby", () => {
  it("opens a confirmation dialog, DELETEs on confirm, and closes the dialog", async () => {
    withDefaults([
      baby(),
      baby({ id: 11, display_name: "Mia", date_of_birth: "2022-05-15" }),
    ]);
    let deleted: number | null = null;
    server.use(
      http.delete(`${BASE}/v1/babies/:id`, ({ params }) => {
        deleted = Number(params.id);
        return HttpResponse.json({ ok: true });
      }),
      // After deletion the client invalidates the babies list — return the
      // remaining baby so the page re-renders cleanly.
      http.get(`${BASE}/v1/babies`, () =>
        HttpResponse.json({
          items:
            deleted === 10
              ? [baby({ id: 11, display_name: "Mia", date_of_birth: "2022-05-15" })]
              : [baby(), baby({ id: 11, display_name: "Mia", date_of_birth: "2022-05-15" })],
        }),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    // Removal now lives inside the baby profile sheet — open it first.
    const card = await screen.findByLabelText("Baby Liam");
    await user.click(within(card).getByRole("button", { name: /open liam's profile/i }));
    await user.click(screen.getByRole("button", { name: /^remove$/i }));

    const dialog = await screen.findByRole("dialog", { name: /remove liam/i });
    expect(within(dialog).getByText(/hide.*feeds.*sleeps/i)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /^remove$/i }));

    await waitFor(() => expect(deleted).toBe(10));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: /remove liam/i })).not.toBeInTheDocument(),
    );
  });

  it("Cancel closes the dialog without deleting", async () => {
    withDefaults([baby()]);
    let calls = 0;
    server.use(
      http.delete(`${BASE}/v1/babies/:id`, () => {
        calls++;
        return HttpResponse.json({ ok: true });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    const card = await screen.findByLabelText("Baby Liam");
    await user.click(within(card).getByRole("button", { name: /open liam's profile/i }));
    await user.click(screen.getByRole("button", { name: /^remove$/i }));
    const dialog = await screen.findByRole("dialog", { name: /remove liam/i });
    await user.click(within(dialog).getByRole("button", { name: /cancel/i }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: /remove liam/i })).not.toBeInTheDocument(),
    );
    expect(calls).toBe(0);
  });
});

describe("ProfilePage — US5 add baby", () => {
  it("opens the modal, POSTs the new baby, and closes on success", async () => {
    withDefaults([baby()]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/v1/babies`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          baby({ id: 12, display_name: String(created?.display_name ?? ""), date_of_birth: String(created?.date_of_birth ?? "") }),
        );
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<ProfilePage user={USER} onBack={() => {}} />);
    await screen.findByText("Liam");
    await user.click(screen.getByRole("button", { name: /add a baby/i }));

    const dialog = await screen.findByRole("dialog", { name: /add a baby/i });
    await user.type(within(dialog).getByLabelText(/name/i), "Noah");
    await user.type(within(dialog).getByLabelText(/date of birth/i), "2025-09-10");
    await user.click(within(dialog).getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(created).toMatchObject({ display_name: "Noah", date_of_birth: "2025-09-10" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /add a baby/i })).not.toBeInTheDocument());
  });
});
