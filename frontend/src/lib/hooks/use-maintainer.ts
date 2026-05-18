"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { maintainerApi, authApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cacheConfig } from "@/lib/query-client";

export function useMaintainerOverview() {
  return useQuery({
    queryKey: queryKeys.maintainer.overview,
    queryFn: ({ signal }) =>
      maintainerApi.getOverview(signal).then((r) => r.data),
    staleTime: cacheConfig.maintainer.overview.staleTime,
    gcTime: cacheConfig.maintainer.overview.gcTime,
    retry: 2,
  });
}

export function useRepoDetail(repoId: number | null) {
  return useQuery({
    queryKey: queryKeys.maintainer.repoDetail(repoId!),
    queryFn: ({ signal }) =>
      maintainerApi.getRepoDetail(repoId!, signal).then((r) => r.data),
    enabled: repoId !== null,
    staleTime: cacheConfig.maintainer.repoDetail.staleTime,
    gcTime: cacheConfig.maintainer.repoDetail.gcTime,
    retry: 1,
  });
}

export function useSuggestedContributors(
  repoId: number | null,
  params?: { limit?: number }
) {
  return useQuery({
    queryKey: queryKeys.maintainer.contributors(
      repoId!,
      params as Record<string, unknown>
    ),
    queryFn: ({ signal }) =>
      maintainerApi
        .getSuggestedContributors(repoId!, params, signal)
        .then((r) => r.data),
    enabled: repoId !== null,
    staleTime: cacheConfig.maintainer.contributors.staleTime,
    gcTime: cacheConfig.maintainer.contributors.gcTime,
    retry: 1,
  });
}

export function useMaintainerSyncUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      github_id: number;
      github_username: string;
    }) => authApi.githubCallback(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.maintainer.overview,
      });
    },
    retry: 1,
  });
}
