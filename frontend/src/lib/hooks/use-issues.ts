"use client";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { issuesApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cacheConfig } from "@/lib/query-client";

type MatchesParams = Parameters<typeof issuesApi.getMatches>[0];

export function useMatches(params?: MatchesParams) {
  return useQuery({
    queryKey: queryKeys.issues.matches(
      params as Record<string, unknown> | undefined
    ),
    queryFn: ({ signal }) =>
      issuesApi.getMatches(params, signal).then((r) => r.data),
    staleTime: cacheConfig.issues.matches.staleTime,
    gcTime: cacheConfig.issues.matches.gcTime,
    retry: 2,
  });
}

type SearchParams = Parameters<typeof issuesApi.search>[0];

export function useSearch(params: SearchParams | null) {
  return useQuery({
    queryKey: queryKeys.issues.search(
      (params ?? {}) as Record<string, unknown>
    ),
    queryFn: ({ signal }) =>
      issuesApi.search(params!, signal).then((r) => r.data),
    enabled: !!params && !!params.q?.trim(),
    staleTime: cacheConfig.issues.search.staleTime,
    gcTime: cacheConfig.issues.search.gcTime,
    retry: 1,
  });
}

type SmartSearchParams = Parameters<typeof issuesApi.smartSearch>[0];

export function useSmartSearch(params: SmartSearchParams | null) {
  return useQuery({
    queryKey: queryKeys.issues.smartSearch(
      (params ?? {}) as Record<string, unknown>
    ),
    queryFn: ({ signal }) =>
      issuesApi.smartSearch(params!, signal).then((r) => r.data),
    enabled: !!params && !!params.q?.trim(),
    staleTime: cacheConfig.issues.smartSearch.staleTime,
    gcTime: cacheConfig.issues.smartSearch.gcTime,
    retry: 1,
  });
}

type TrendingParams = Parameters<typeof issuesApi.getTrending>[0];

export function useTrending(params?: TrendingParams) {
  return useQuery({
    queryKey: queryKeys.issues.trending(
      params as Record<string, unknown> | undefined
    ),
    queryFn: ({ signal }) =>
      issuesApi.getTrending(params, signal).then((r) => r.data),
    staleTime: cacheConfig.issues.trending.staleTime,
    gcTime: cacheConfig.issues.trending.gcTime,
    retry: 2,
  });
}

export function useSavedIssues() {
  return useQuery({
    queryKey: queryKeys.issues.saved,
    queryFn: ({ signal }) =>
      issuesApi.getSavedIssues(signal).then((r) => r.data),
    staleTime: cacheConfig.issues.saved.staleTime,
    gcTime: cacheConfig.issues.saved.gcTime,
    retry: 1,
  });
}

export function useSaveIssue() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (issueId: number) =>
      issuesApi.saveIssue(issueId).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.issues.matches(),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.issues.saved,
      });
    },
    retry: 1,
  });
}

export function useTriggerIndex() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (languages: string[] | undefined) =>
      issuesApi.triggerIndex(languages).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.issues.matches(),
      });
    },
    retry: 0,
  });
}
