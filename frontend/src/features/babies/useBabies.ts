import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError, setActiveBabyId } from "@/shared/apiClient";
import type { Baby, BabyCreate, BabyListResponse, BabyUpdate } from "@/shared/types";
import { SESSION_QUERY_KEY } from "../auth/useSession";

export const BABIES_QUERY_KEY = ["babies"] as const;

export function useBabies(enabled = true) {
  return useQuery<BabyListResponse, ApiError>({
    queryKey: BABIES_QUERY_KEY,
    queryFn: () => apiClient.listBabies(),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateBabyMutation() {
  const qc = useQueryClient();
  return useMutation<Baby, ApiError, BabyCreate>({
    mutationFn: (body) => apiClient.createBaby(body),
    onSuccess: (baby) => {
      qc.invalidateQueries({ queryKey: BABIES_QUERY_KEY });
      // Backend auto-activates the first baby; mirror that in the header.
      setActiveBabyId(baby.id);
      qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    },
  });
}

export function useUpdateBabyMutation() {
  const qc = useQueryClient();
  return useMutation<Baby, ApiError, { id: number; body: BabyUpdate }>({
    mutationFn: ({ id, body }) => apiClient.updateBaby(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: BABIES_QUERY_KEY }),
  });
}

export function useDeleteBabyMutation() {
  const qc = useQueryClient();
  return useMutation<{ ok: true }, ApiError, number>({
    mutationFn: (id) => apiClient.deleteBaby(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: BABIES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    },
  });
}

export function useSetActiveBabyMutation() {
  const qc = useQueryClient();
  return useMutation<{ user: { id: number; active_baby_id: number | null } }, ApiError, number>({
    mutationFn: async (baby_id) => {
      const res = await apiClient.setActiveBaby({ baby_id });
      setActiveBabyId(res.user.active_baby_id);
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
      // Diary lists are baby-scoped server-side, so invalidate everything.
      qc.invalidateQueries({
        predicate: (q) => {
          const k = q.queryKey[0];
          return k === "feeds" || k === "sleeps" || k === "poops" || k === "appointments";
        },
      });
    },
  });
}
