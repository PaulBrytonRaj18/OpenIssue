"use client";
import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Filter, RefreshCw, Zap, AlertCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { IssueCard } from "@/components/IssueCard";
import { SkillFingerprintPanel } from "@/components/SkillFingerprint";
import { EmptyState } from "@/components/EmptyState";
import { PageLoader } from "@/components/Spinner";
import { issuesApi, githubApi, authApi } from "@/lib/api";
import { IssueMatchResponse, SkillFingerprint } from "@/lib/types";

const LANGUAGES = [
  "All", "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "Ruby", "PHP",
];
const LABELS = [
  { value: "", label: "All Issues" },
  { value: "good_first", label: "Good First Issue" },
  { value: "help_wanted", label: "Help Wanted" },
];

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [matchData, setMatchData] = useState<IssueMatchResponse | null>(null);
  const [fingerprint, setFingerprint] = useState<SkillFingerprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [langFilter, setLangFilter] = useState("All");
  const [labelFilter, setLabelFilter] = useState("");

  const user = session?.user as {
    username?: string;
    githubId?: number;
    avatarUrl?: string;
    name?: string;
    email?: string;
    bio?: string;
    publicRepos?: number;
    followers?: number;
  };

  // Sync user to backend after login
  const syncUserToBackend = useCallback(async () => {
    if (!user?.username || !user?.githubId) return;
    try {
      const res = await authApi.githubCallback({
        github_id: user.githubId,
        github_username: user.username,
        github_avatar_url: user.avatarUrl,
        github_name: user.name ?? undefined,
        github_bio: (user as { bio?: string }).bio,
        email: user.email ?? undefined,
        public_repos: (user as { publicRepos?: number }).publicRepos ?? 0,
        followers: (user as { followers?: number }).followers ?? 0,
      });
      // Store JWT for subsequent API calls
      if (res.data?.access_token) {
        localStorage.setItem("issuecompass_token", res.data.access_token);
      }
      return res.data;
    } catch (e) {
      console.error("Failed to sync user to backend", e);
    }
  }, [user]);

  // Analyze GitHub profile for skill fingerprint
  const analyzeProfile = useCallback(async () => {
    if (!user?.username) return;
    setAnalyzing(true);
    try {
      await githubApi.analyzeProfile(user.username);
    } catch (e) {
      console.error("Analyze failed", e);
    } finally {
      setAnalyzing(false);
    }
  }, [user?.username]);

  // Fetch matched issues
  const fetchMatches = useCallback(async () => {
    try {
      const params: Record<string, string | number> = { limit: 30 };
      if (langFilter !== "All") params.language = langFilter;
      if (labelFilter) params.label = labelFilter;

      const res = await issuesApi.getMatches(params as { language?: string; label?: string; limit?: number });
      setMatchData(res.data);
      if (res.data.user_skills) setFingerprint(res.data.user_skills);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      if (err?.response?.status === 401 || err?.response?.status === 422) {
        // Token missing or expired, re-sync
        await syncUserToBackend();
      } else {
        setError("Failed to load matches. Make sure the backend is running.");
      }
    }
  }, [langFilter, labelFilter, syncUserToBackend]);

  // Boot sequence
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
      return;
    }
    if (status !== "authenticated") return;

    const boot = async () => {
      setLoading(true);
      setError(null);
      await syncUserToBackend();
      await analyzeProfile();
      await fetchMatches();
      setLoading(false);
    };

    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Re-fetch when filters change
  useEffect(() => {
    if (!loading && status === "authenticated") {
      fetchMatches();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [langFilter, labelFilter]);

  if (status === "loading" || loading) {
    return (
      <>
        <Navbar />
        <PageLoader
          message={
            analyzing
              ? "Analyzing your GitHub profile..."
              : "Loading your matches..."
          }
        />
      </>
    );
  }

  const matches = matchData?.matches ?? [];
  const noSkills = !fingerprint;
  const noMatches = matches.length === 0;

  return (
    <>
      <Navbar />
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex gap-8">
          {/* ── Sidebar ─────────────────────────────────── */}
          <aside className="hidden lg:block w-72 flex-shrink-0">
            <div className="sticky top-20 space-y-4">
              {/* Welcome */}
              <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-[var(--foreground)]">
                    Hey, {user?.name?.split(" ")[0] || user?.username} 👋
                  </span>
                </div>
                <p className="text-xs text-[var(--muted)]">
                  Here are your personalized issue matches.
                </p>
              </div>

              {/* Skill Fingerprint */}
              {fingerprint ? (
                <>
                  <div className="flex items-center justify-between px-1">
                    <span className="text-xs font-mono text-[var(--muted)]">
                      Your Skill Fingerprint
                    </span>
                    <button
                      onClick={analyzeProfile}
                      disabled={analyzing}
                      className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors disabled:opacity-50"
                      title="Refresh skill analysis"
                    >
                      <RefreshCw
                        size={12}
                        className={analyzing ? "animate-spin" : ""}
                      />
                    </button>
                  </div>
                  <SkillFingerprintPanel fingerprint={fingerprint} />
                </>
              ) : (
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] text-center">
                  <Zap size={20} className="text-[var(--accent)] mx-auto mb-2" />
                  <p className="text-xs text-[var(--muted)]">
                    Building your skill fingerprint from GitHub...
                  </p>
                  <button
                    onClick={analyzeProfile}
                    disabled={analyzing}
                    className="mt-3 text-xs text-[var(--accent)] hover:opacity-80"
                  >
                    {analyzing ? "Analyzing..." : "Re-analyze"}
                  </button>
                </div>
              )}
            </div>
          </aside>

          {/* ── Main Feed ───────────────────────────────── */}
          <main className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="font-display text-2xl font-bold text-[var(--foreground)]">
                  Your Matches
                </h1>
                <p className="text-sm text-[var(--muted)] mt-0.5">
                  {matches.length > 0
                    ? `${matches.length} issues matched to your skills`
                    : "No matches yet — try indexing issues"}
                </p>
              </div>
              <button
                onClick={fetchMatches}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors"
              >
                <RefreshCw size={12} />
                Refresh
              </button>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2 mb-6">
              <Filter size={13} className="text-[var(--muted)]" />

              {/* Language filter */}
              <div className="flex items-center gap-1 flex-wrap">
                {LANGUAGES.map((lang) => (
                  <button
                    key={lang}
                    onClick={() => setLangFilter(lang)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
                      langFilter === lang
                        ? "bg-[var(--accent-dim)] text-[var(--accent)] border border-[var(--accent-dim)]"
                        : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {lang}
                  </button>
                ))}
              </div>

              {/* Label filter */}
              <select
                value={labelFilter}
                onChange={(e) => setLabelFilter(e.target.value)}
                className="ml-auto px-3 py-1 rounded-lg text-xs border border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] focus:outline-none focus:border-[var(--border-bright)]"
              >
                {LABELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-3 p-4 rounded-xl border border-[var(--danger)] bg-[rgba(248,81,73,0.08)] mb-6">
                <AlertCircle size={16} className="text-[var(--danger)] flex-shrink-0" />
                <div>
                  <p className="text-sm text-[var(--danger)] font-medium">
                    Connection Error
                  </p>
                  <p className="text-xs text-[var(--muted)] mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* No matches */}
            {noMatches && !error && (
              <EmptyState
                icon={<Zap size={22} />}
                title={noSkills ? "Building your fingerprint" : "No matches yet"}
                description={
                  noSkills
                    ? "We're analyzing your GitHub repos. This takes a few seconds."
                    : "No indexed issues match your skills yet. Try triggering an index or adjusting filters."
                }
                action={
                  <button
                    onClick={async () => {
                      await issuesApi.triggerIndex();
                      setTimeout(fetchMatches, 3000);
                    }}
                    className="px-6 py-2.5 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold"
                  >
                    Index Issues Now
                  </button>
                }
              />
            )}

            {/* Issue cards */}
            {!noMatches && (
              <div className="space-y-4">
                {matches.map((match, i) => (
                  <IssueCard key={match.issue.id} match={match} index={i} />
                ))}
              </div>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
