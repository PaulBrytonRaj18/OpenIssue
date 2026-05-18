import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
  withCredentials: true,
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isCancel(error)) return Promise.reject(error);
    const config = error.config;
    if (!config || config._retry) return Promise.reject(error);
    const isServerError = error.response?.status >= 500;
    const isNetworkError = !error.response && error.code === "ERR_NETWORK";
    if ((isServerError || isNetworkError) && !config._retry) {
      config._retry = true;
      await new Promise((r) => setTimeout(r, 1000));
      return api(config);
    }
    return Promise.reject(error);
  }
);

export function makeCancelable() {
  const controller = new AbortController();
  return { signal: controller.signal, cancel: () => controller.abort() };
}

export const authApi = {
  githubCallback: (data: {
    github_id: number;
    github_username: string;
    github_avatar_url?: string;
    github_name?: string;
    github_bio?: string;
    email?: string;
    public_repos?: number;
    followers?: number;
  }) => api.post("/auth/github/callback", data),

  getMe: (signal?: AbortSignal) =>
    api.get("/auth/me", { signal }),

  refreshToken: () =>
    api.post("/auth/refresh"),
};

export const githubApi = {
  analyzeProfile: (username: string) =>
    api.post(`/github/analyze/${username}`),

  getFingerprint: (signal?: AbortSignal) =>
    api.get("/github/fingerprint", { signal }),

  getGitHubUser: (username: string, signal?: AbortSignal) =>
    api.get(`/github/user/${username}`, { signal }),
};

export const issuesApi = {
  getMatches: (
    params?: {
      language?: string;
      label?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) => api.get("/issues/matches", { params, signal }),

  search: (
    params: {
      q: string;
      language?: string;
      difficulty?: string;
      label?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) => api.get("/issues/search", { params, signal }),

  getTrending: (
    params?: {
      language?: string;
      limit?: number;
    },
    signal?: AbortSignal
  ) => api.get("/issues/trending", { params, signal }),

  triggerIndex: (languages?: string[]) =>
    api.post("/issues/index", null, {
      params: { languages: languages?.join(",") },
    }),

  saveIssue: (issueId: number) =>
    api.post(`/issues/save/${issueId}`),

  getSavedIssues: (signal?: AbortSignal) =>
    api.get("/issues/saved", { signal }),

  getStats: (signal?: AbortSignal) =>
    api.get("/issues/stats", { signal }),

  smartSearch: (
    params: {
      q: string;
      language?: string;
      difficulty?: string;
      label?: string;
      limit?: number;
      offset?: number;
    },
    signal?: AbortSignal
  ) => api.get("/issues/smart-search", { params, signal }),
};

export const searchesApi = {
  getSuggestions: (q: string, signal?: AbortSignal) =>
    api.get("/searches/suggestions", { params: { q }, signal }),

  saveSearch: (data: {
    name: string;
    query: string;
    filters?: Record<string, unknown>;
    notify?: boolean;
  }) => api.post("/searches/save", data),

  listSearches: (signal?: AbortSignal) =>
    api.get("/searches/", { signal }),

  getSearch: (id: number, signal?: AbortSignal) =>
    api.get(`/searches/${id}`, { signal }),

  updateSearch: (id: number, data: {
    name?: string;
    notify?: boolean;
  }) => api.put(`/searches/${id}`, data),

  deleteSearch: (id: number) =>
    api.delete(`/searches/${id}`),

  checkSearch: (id: number) =>
    api.post(`/searches/${id}/check`),
};

export const maintainerApi = {
  getOverview: (signal?: AbortSignal) =>
    api.get("/maintainer/overview", { signal }),

  getRepoDetail: (repoId: number, signal?: AbortSignal) =>
    api.get(`/maintainer/repos/${repoId}`, { signal }),

  getSuggestedContributors: (
    repoId: number,
    params?: { limit?: number },
    signal?: AbortSignal
  ) => api.get(`/maintainer/repos/${repoId}/contributors`, { params, signal }),
};

export default api;
