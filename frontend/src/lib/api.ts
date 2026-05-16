import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Attach token from localStorage if present
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    let token = localStorage.getItem("issuecompass_token");
    // Backward compat: fallback to old key
    if (!token) {
      token = localStorage.getItem("openissue_token");
      if (token) localStorage.setItem("issuecompass_token", token);
    }
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ─── Auth ─────────────────────────────────────────────────────
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

  getMe: () =>
    api.get("/auth/me"),

  refreshToken: () =>
    api.post("/auth/refresh"),
};

// ─── GitHub ───────────────────────────────────────────────────
export const githubApi = {
  analyzeProfile: (username: string) =>
    api.post(`/github/analyze/${username}`),

  getFingerprint: () =>
    api.get("/github/fingerprint"),

  getGitHubUser: (username: string) =>
    api.get(`/github/user/${username}`),
};

// ─── Issues ───────────────────────────────────────────────────
export const issuesApi = {
  getMatches: (params?: {
    language?: string;
    label?: string;
    limit?: number;
    offset?: number;
  }) => api.get("/issues/matches", { params }),

  search: (params: {
    q: string;
    language?: string;
    difficulty?: string;
    label?: string;
    limit?: number;
    offset?: number;
  }) => api.get("/issues/search", { params }),

  getTrending: (params?: {
    language?: string;
    limit?: number;
  }) => api.get("/issues/trending", { params }),

  triggerIndex: (languages?: string[]) =>
    api.post("/issues/index", null, {
      params: { languages: languages?.join(",") },
    }),

  saveIssue: (issueId: number) =>
    api.post(`/issues/save/${issueId}`),

  getSavedIssues: () =>
    api.get("/issues/saved"),

  getStats: () =>
    api.get("/issues/stats"),

  smartSearch: (params: {
    q: string;
    language?: string;
    difficulty?: string;
    label?: string;
    limit?: number;
    offset?: number;
  }) => api.get("/issues/smart-search", { params }),
};

// ─── Saved Searches ────────────────────────────────────────────
export const searchesApi = {
  getSuggestions: (q: string) =>
    api.get("/searches/suggestions", { params: { q } }),

  saveSearch: (data: {
    name: string;
    query: string;
    filters?: Record<string, unknown>;
    notify?: boolean;
  }) => api.post("/searches/save", data),

  listSearches: () =>
    api.get("/searches/"),

  getSearch: (id: number) =>
    api.get(`/searches/${id}`),

  updateSearch: (id: number, data: {
    name?: string;
    notify?: boolean;
  }) => api.put(`/searches/${id}`, data),

  deleteSearch: (id: number) =>
    api.delete(`/searches/${id}`),

  checkSearch: (id: number) =>
    api.post(`/searches/${id}/check`),
};

export default api;
