import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";

export function usePoops(date: Date) {
  return useQuery({
    queryKey: queryKeys.poops(date),
    queryFn: () => apiClient.getPoops(date),
  });
}
