import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";

export function useSleeps(date: Date) {
  return useQuery({
    queryKey: queryKeys.sleeps(date),
    queryFn: () => apiClient.getSleeps(date),
  });
}
