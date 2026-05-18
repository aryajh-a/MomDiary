import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/features/chat/ChatPanel";
import created from "../fixtures/entries.created.json";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("ChatPanel — success path", () => {
  it("sends a message and shows the assistant confirmation", async () => {
    let captured: unknown = null;
    server.use(
      http.post(`${BASE}/v1/entries`, async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json(created);
      }),
    );

    renderWithProviders(<ChatPanel />);

    const input = screen.getByLabelText(/message/i);
    await userEvent.type(input, "120 ml breast milk just now");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/Logged 120 ml of breast milk\./)).toBeInTheDocument(),
    );
    expect(captured).toEqual({ message: "120 ml breast milk just now" });
  });

  it("disables submit while in-flight and re-enables after", async () => {
    server.use(
      http.post(`${BASE}/v1/entries`, async () => {
        await new Promise((r) => setTimeout(r, 30));
        return HttpResponse.json(created);
      }),
    );
    renderWithProviders(<ChatPanel />);
    await userEvent.type(screen.getByLabelText(/message/i), "x");
    const send = screen.getByRole("button", { name: /send/i });
    await userEvent.click(send);
    expect(send).toBeDisabled();
    await waitFor(() => expect(screen.getByText(/Logged 120 ml/)).toBeInTheDocument());
  });
});
