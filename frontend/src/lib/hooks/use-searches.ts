"use client";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { searchesApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cacheConfig } from "@/lib/query-client";

export function useSuggestions(q: string) {
  return useQuery({
    queryKey: queryKeys.searches.suggestions(q),
    queryFn: ({ signal }) =>
      searchesApi.getSuggestions(q, signal).then((r) => r.data),
    enabled: q.trim().length >= 2,
    staleTime: cacheConfig.searches.suggestions.staleTime,
    gcTime: cacheConfig.searches.suggestions.gcTime,
    retry: 0,
  });
}

export function useSavedSearches() {
  return useQuery({
    queryKey: queryKeys.searches.list,
    queryFn: ({ signal }) =>
      searchesApi.listSearches(signal).then((r) => r.data),
    staleTime: cacheConfig.searches.list.staleTime,
    gcTime: cacheConfig.searches.list.gcTime,
    retry: 1,
  });
}

export function useSaveSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      data: Parameters<typeof searchesApi.saveSearch>[0]
    ) => searchesApi.saveSearch(data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.searches.list,
      });
    },
    retry: 0,
  });
}

export function useUpdateSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof searchesApi.updateSearch>[1];
    }) => searchesApi.updateSearch(id, data).then((r) => r.data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.searches.list,
      });
      const previous = queryClient.getQueryData(queryKeys.searches.list);
      queryClient.setQueryData(queryKeys.searches.list, (old: unknown) => {
        const arr = old as Array<Record<string, unknown>>;
        if (!Array.isArray(arr)) return old;
        return arr.map((s) =>
          s.id === id ? { ...s, ...data } : s
        );
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.searches.list,
          context.previous
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.searches.list,
      });
    },
    retry: 1,
  });
}

export function useDeleteSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) =>
      searchesApi.deleteSearch(id).then((r) => r.data),
    onMutate: async (id) => {
      await queryClient.cancelQueries({
        queryKey: queryKeys.searches.list,
      });
      const previous = queryClient.getQueryData(queryKeys.searches.list);
      queryClient.setQueryData(queryKeys.searches.list, (old: unknown) => {
        const arr = old as Array<Record<string, unknown>>;
        if (!Array.isArray(arr)) return old;
        return arr.filter((s) => s.id !== id);
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.searches.list,
          context.previous
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.searches.list,
      });
    },
    retry: 1,
  });
}

export function useCheckSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) =>
      searchesApi.checkSearch(id).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.searches.list,
      });
    },
    retry: 1,
  });
}
