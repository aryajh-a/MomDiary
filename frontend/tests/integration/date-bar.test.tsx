import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { format } from "date-fns";
import { DateBar } from "@/features/date/DateBar";
import { renderWithProviders } from "../_msw/renderWithProviders";
import { queryKeys } from "@/shared/queryKeys";

describe("DateBar", () => {
  it("defaults to today", () => {
    renderWithProviders(<DateBar />);
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("prev/next buttons shift the heading by one day and invalidate the four section keys", async () => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    const { client } = renderWithProviders(<DateBar />);

    let invalidated: unknown[][] = [];
    const origInvalidate = client.invalidateQueries.bind(client);
    client.invalidateQueries = ((arg: { queryKey: unknown[] }) => {
      invalidated.push(arg.queryKey);
      return origInvalidate(arg);
    }) as typeof client.invalidateQueries;

    await userEvent.click(screen.getByRole("button", { name: /previous day/i }));
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    // Four keys for the new date were invalidated.
    expect(invalidated.map((k) => (k as string[])[0])).toEqual([
      "feeds",
      "sleeps",
      "poops",
      "appointments",
    ]);
    expect(invalidated[0]).toEqual([...queryKeys.feeds(yesterday)]);
  });

  it("picking a date in the input updates the heading", () => {
    renderWithProviders(<DateBar />);
    const input = screen.getByLabelText(/pick a date/i) as HTMLInputElement;
    const target = new Date();
    target.setDate(target.getDate() + 7);
    const value = format(target, "yyyy-MM-dd");
    fireEvent.change(input, { target: { value } });
    expect(input.value).toBe(value);
  });
});
