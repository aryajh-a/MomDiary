import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { server } from "../_msw/setup";
import { renderWithProviders } from "../_msw/renderWithProviders";

const BASE = "http://localhost:8000";

describe("ChatPanel — error", () => {
  it("renders an assistant error, surfaces correlation_id, preserves the draft", async () => {
    server.use(
      http.post(`${BASE}/v1/entries`, () =>
        HttpResponse.json(
          { error: "validation_error", message: "bad", correlation_id: "cid-err" },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<ChatPanel />);
    const input = screen.getByLabelText(/message/i) as HTMLTextAreaElement;
    await userEvent.type(input, "garbage input");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText(/Something went wrong saving that/)).toBeInTheDocument());
    expect(screen.getByText("cid-err")).toBeInTheDocument();
    expect(input.value).toBe("garbage input");
  });
});
