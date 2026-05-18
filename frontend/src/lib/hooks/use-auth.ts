"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useSyncUserToBackend() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Parameters<typeof authApi.githubCallback>[0]) =>
      authApi.githubCallback(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.all });
    },
    retry: 1,
  });
}
