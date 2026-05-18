import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/apiClient";
import { queryKeys } from "@/shared/queryKeys";

export function useAppointments(date: Date) {
  return useQuery({
    queryKey: queryKeys.appointments(date),
    queryFn: () => apiClient.getAppointments(date),
  });
}
