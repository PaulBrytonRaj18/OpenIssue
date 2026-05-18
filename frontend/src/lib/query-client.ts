import { QueryClient } from "@tanstack/react-query";

const STALE_TIMES = {
  SHORT: 30 * 1000,
  MEDIUM: 5 * 60 * 1000,
  LONG: 30 * 60 * 1000,
  INFINITY: Infinity,
} as const;

const GC_TIMES = {
  SHORT: 60 * 1000,
  MEDIUM: 15 * 60 * 1000,
  LONG: 60 * 60 * 1000,
} as const;

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIMES.SHORT,
        gcTime: GC_TIMES.SHORT,
        retry: 2,
        retryDelay: (attemptIndex) =>
          Math.min(1000 * Math.pow(2, attemptIndex), 10000),
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

export const cacheConfig = {
  auth: {
    staleTime: STALE_TIMES.INFINITY,
    gcTime: GC_TIMES.LONG,
  },
  github: {
    fingerprint: {
      staleTime: STALE_TIMES.LONG,
      gcTime: GC_TIMES.LONG,
    },
    user: {
      staleTime: STALE_TIMES.LONG,
      gcTime: GC_TIMES.LONG,
    },
    analyze: {
      staleTime: STALE_TIMES.INFINITY,
      gcTime: GC_TIMES.SHORT,
    },
  },
  issues: {
    matches: {
      staleTime: STALE_TIMES.SHORT,
      gcTime: GC_TIMES.MEDIUM,
    },
    search: {
      staleTime: STALE_TIMES.SHORT,
      gcTime: GC_TIMES.MEDIUM,
    },
    smartSearch: {
      staleTime: STALE_TIMES.SHORT,
      gcTime: GC_TIMES.MEDIUM,
    },
    trending: {
      staleTime: 2 * 60 * 1000,
      gcTime: GC_TIMES.MEDIUM,
    },
    saved: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.MEDIUM,
    },
  },
  searches: {
    list: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.MEDIUM,
    },
    suggestions: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.SHORT,
    },
  },
  maintainer: {
    overview: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.MEDIUM,
    },
    repoDetail: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.MEDIUM,
    },
    contributors: {
      staleTime: STALE_TIMES.MEDIUM,
      gcTime: GC_TIMES.MEDIUM,
    },
  },
} as const;
