import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";

export function useFeeds(date: Date) {
  return useQuery({
    queryKey: queryKeys.feeds(date),
    queryFn: () => apiClient.getFeeds(date),
  });
}
