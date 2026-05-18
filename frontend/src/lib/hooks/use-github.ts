"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { githubApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cacheConfig } from "@/lib/query-client";

export function useFingerprint() {
  return useQuery({
    queryKey: queryKeys.github.fingerprint,
    queryFn: ({ signal }) =>
      githubApi.getFingerprint(signal).then((r) => r.data),
    staleTime: cacheConfig.github.fingerprint.staleTime,
    gcTime: cacheConfig.github.fingerprint.gcTime,
    retry: 1,
  });
}

export function useGitHubUser(username: string) {
  return useQuery({
    queryKey: queryKeys.github.user(username),
    queryFn: ({ signal }) =>
      githubApi.getGitHubUser(username, signal).then((r) => r.data),
    staleTime: cacheConfig.github.user.staleTime,
    gcTime: cacheConfig.github.user.gcTime,
    enabled: !!username,
    retry: 1,
  });
}

export function useAnalyzeProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (username: string) =>
      githubApi.analyzeProfile(username).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.github.fingerprint,
      });
    },
    retry: 1,
  });
}
