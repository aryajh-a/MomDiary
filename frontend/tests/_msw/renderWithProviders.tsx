import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { SelectedDateProvider } from "@/features/date/useSelectedDate";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options: {
    client?: QueryClient;
    selectedDate?: Date;
    renderOptions?: Omit<RenderOptions, "wrapper">;
  } = {},
): RenderResult & { client: QueryClient } {
  const client = options.client ?? makeQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <SelectedDateProvider initialDate={options.selectedDate ?? new Date()}>
        {children}
      </SelectedDateProvider>
    </QueryClientProvider>
  );
  const result = render(ui, { wrapper: Wrapper, ...options.renderOptions });
  return Object.assign(result, { client });
}
