export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    me: ["auth", "me"] as const,
  },
  github: {
    all: ["github"] as const,
    fingerprint: ["github", "fingerprint"] as const,
    user: (username: string) => ["github", "user", username] as const,
    analyze: (username: string) => ["github", "analyze", username] as const,
  },
  issues: {
    all: ["issues"] as const,
    matches: (params?: Record<string, unknown>) =>
      ["issues", "matches", params ?? {}] as const,
    search: (params: Record<string, unknown>) =>
      ["issues", "search", params] as const,
    smartSearch: (params: Record<string, unknown>) =>
      ["issues", "smart-search", params] as const,
    trending: (params?: Record<string, unknown>) =>
      ["issues", "trending", params ?? {}] as const,
    saved: ["issues", "saved"] as const,
  },
  searches: {
    all: ["searches"] as const,
    list: ["searches", "list"] as const,
    suggestions: (q: string) => ["searches", "suggestions", q] as const,
  },
  maintainer: {
    all: ["maintainer"] as const,
    overview: ["maintainer", "overview"] as const,
    repoDetail: (repoId: number) => ["maintainer", "repos", repoId] as const,
    contributors: (repoId: number, params?: Record<string, unknown>) =>
      ["maintainer", "repos", repoId, "contributors", params ?? {}] as const,
  },
} as const;
