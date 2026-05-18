export interface User {
  id: number;
  github_username: string;
  github_avatar_url: string | null;
  github_name: string | null;
  github_bio: string | null;
  public_repos: number;
  followers: number;
  skill_json: SkillFingerprint | null;
  skill_last_updated: string | null;
  created_at: string;
}

export interface SkillFingerprint {
  languages: Record<string, number>;
  topics: string[];
  categories: Record<string, string[]>;
  experience_level: "beginner" | "intermediate" | "advanced";
  top_skills: string[];
  total_repos: number;
  total_stars_received: number;
}

export interface Repository {
  id: number;
  full_name: string;
  name: string;
  description: string | null;
  owner_login: string;
  html_url: string;
  stars: number;
  primary_language: string | null;
  topics: string[] | null;
}

export interface Issue {
  id: number;
  github_id: number;
  number: number;
  title: string;
  body: string | null;
  html_url: string;
  state: string;
  labels: string[] | null;
  is_good_first_issue: boolean;
  is_help_wanted: boolean;
  required_skills: Record<string, unknown> | null;
  complexity_score: number;
  comments: number;
  created_at: string | null;
  repository: Repository | null;
}

export interface MatchedIssue {
  issue: Issue;
  match_score: number;
  matching_skills: string[];
  why_matched: string;
}

export interface IssueMatchResponse {
  matches: MatchedIssue[];
  total: number;
  user_skills: SkillFingerprint | null;
}

export interface PlatformStats {
  total_users: number;
  total_issues_indexed: number;
  total_repos_indexed: number;
}

export interface SearchResult {
  matches: MatchedIssue[];
  total: number;
  query: string;
}

export interface TrendingResult {
  matches: MatchedIssue[];
  total: number;
  language: string | null;
}

export interface SmartSearchResult {
  matches: MatchedIssue[];
  total: number;
  query: string;
  intent: {
    keywords: string[];
    languages: string[];
    difficulty: string | null;
    labels: string[];
    categories: string[];
  } | null;
  personalized: boolean;
}

export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  filters: Record<string, unknown> | null;
  notify: boolean;
  created_at: string;
  last_checked_at: string | null;
}

export interface SuggestionItem {
  type: string;
  text: string;
  description: string | null;
}

export interface SuggestionResult {
  suggestions: SuggestionItem[];
}

// Complexity label
export function complexityLabel(score: number): string {
  if (score < 0.35) return "Beginner";
  if (score < 0.65) return "Intermediate";
  return "Advanced";
}

export function complexityColor(score: number): string {
  if (score < 0.35) return "#3fb950";
  if (score < 0.65) return "#e3b341";
  return "#f85149";
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "unknown";
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export interface MaintainerRepo {
  id: number;
  full_name: string;
  name: string;
  description: string | null;
  owner_login: string;
  html_url: string;
  stars: number;
  forks: number;
  primary_language: string | null;
  open_issues_count: number;
  total_issues: number;
  good_first_issues: number;
  help_wanted_issues: number;
  avg_complexity: number;
}

export interface MaintainerRepoDetail {
  repo: MaintainerRepo;
  issues: Issue[];
}

export interface ContributorMatch {
  user_id: number;
  github_username: string;
  github_avatar_url: string | null;
  match_score: number;
  matching_skills: string[];
  why_matched: string;
}

export interface MaintainerOverview {
  total_repos: number;
  total_open_issues: number;
  total_good_first_issues: number;
  total_help_wanted_issues: number;
  total_potential_contributors: number;
  repos: MaintainerRepo[];
}

export const LANGUAGE_COLORS: Record<string, string> = {
  python: "#3572A5",
  javascript: "#f1e05a",
  typescript: "#3178c6",
  rust: "#dea584",
  go: "#00ADD8",
  java: "#b07219",
  "c++": "#f34b7d",
  "c#": "#178600",
  ruby: "#701516",
  php: "#4F5D95",
  swift: "#ffac45",
  kotlin: "#A97BFF",
  html: "#e34c26",
  css: "#563d7c",
  shell: "#89e051",
  vue: "#41b883",
  dart: "#00B4AB",
};
