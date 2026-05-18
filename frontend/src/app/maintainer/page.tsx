"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  BookmarkCheck,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  GitFork,
  RefreshCw,
  Star,
  Users,
  AlertCircle,
  Shield,
  MessageSquare,
  Bug,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageLoader } from "@/components/Spinner";
import { EmptyState } from "@/components/EmptyState";
import {
  useMaintainerOverview,
  useRepoDetail,
  useSuggestedContributors,
  useMaintainerSyncUser,
} from "@/lib/hooks/use-maintainer";
import {
  LANGUAGE_COLORS,
} from "@/lib/types";
import type { MaintainerOverview, MaintainerRepoDetail, ContributorMatch } from "@/lib/types";

export default function MaintainerPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [error, setError] = useState<string | null>(null);
  const [expandedRepo, setExpandedRepo] = useState<number | null>(null);

  const user = session?.user as { username?: string };
  const sessionUser = session?.user as { githubId?: number };

  const syncMutation = useMaintainerSyncUser();

  const {
    data: overview,
    isLoading,
    refetch,
  } = useMaintainerOverview();

  const {
    data: repoDetail,
    isLoading: detailLoading,
  } = useRepoDetail(expandedRepo);

  const {
    data: contributors,
    isLoading: contribLoading,
  } = useSuggestedContributors(expandedRepo, { limit: 5 });

  const openRepoDetail = (repoId: number) => {
    if (expandedRepo === repoId) {
      setExpandedRepo(null);
      return;
    }
    setExpandedRepo(repoId);
  };

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
      return;
    }
    if (status !== "authenticated") return;

    const fetchData = async () => {
      const err = overview as { response?: { status?: number } };
      if (err && err?.response?.status === 401 || err?.response?.status === 422) {
        try {
          if (user?.username) {
            await syncMutation.mutateAsync({
              github_id: sessionUser.githubId ?? 0,
              github_username: user.username,
            });
          }
        } catch {
          setError("Session expired. Please sign in again.");
        }
      }
    };
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  if (status === "loading" || (isLoading && !overview)) {
    return (
      <>
        <Navbar />
        <PageLoader message="Loading maintainer dashboard..." />
      </>
    );
  }

  const repos = (overview as MaintainerOverview)?.repos ?? [];

  return (
    <>
      <Navbar />
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Shield size={20} className="text-[var(--accent)]" />
              <h1 className="font-display text-2xl font-bold text-[var(--foreground)]">
                Maintainer Dashboard
              </h1>
            </div>
            <p className="text-sm text-[var(--muted)]">
              Overview of your indexed repositories and their issues
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl border border-[var(--danger)] bg-[rgba(248,81,73,0.08)] mb-6">
            <AlertCircle size={16} className="text-[var(--danger)] flex-shrink-0" />
            <p className="text-sm text-[var(--danger)]">{error}</p>
          </div>
        )}

        {overview && repos.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard
              label="Your Repos"
              value={(overview as MaintainerOverview).total_repos}
              icon={<GitFork size={16} />}
              color="var(--accent)"
            />
            <StatCard
              label="Open Issues"
              value={(overview as MaintainerOverview).total_open_issues}
              icon={<Bug size={16} />}
              color="#58a6ff"
            />
            <StatCard
              label="Good First Issues"
              value={(overview as MaintainerOverview).total_good_first_issues}
              icon={<BookmarkCheck size={16} />}
              color="#3fb950"
            />
            <StatCard
              label="Help Wanted"
              value={(overview as MaintainerOverview).total_help_wanted_issues}
              icon={<AlertCircle size={16} />}
              color="#e3b341"
            />
          </div>
        )}

        {repos.length === 0 && !error && (
          <EmptyState
            icon={<Shield size={22} />}
            title="No indexed repositories found"
            description="Repositories you own on GitHub need to be indexed first. Go to the Dashboard and click 'Index Issues Now', or ensure your repos are public."
            action={
              <button
                onClick={() => router.push("/dashboard")}
                className="px-6 py-2.5 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold"
              >
                Go to Dashboard
              </button>
            }
          />
        )}

        {repos.length > 0 && (
          <div className="space-y-3">
            {repos.map((repo) => (
              <div
                key={repo.id}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden transition-colors"
              >
                <button
                  onClick={() => openRepoDetail(repo.id)}
                  className="w-full flex items-center justify-between p-4 hover:bg-[var(--surface-2)] transition-colors text-left"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="flex-shrink-0">
                      {expandedRepo === repo.id ? (
                        <ChevronDown size={16} className="text-[var(--accent)]" />
                      ) : (
                        <ChevronRight size={16} className="text-[var(--muted)]" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--foreground)] truncate">
                          {repo.full_name}
                        </span>
                        {repo.primary_language && (
                          <span
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{
                              background:
                                LANGUAGE_COLORS[repo.primary_language.toLowerCase()] ?? "#8b949e",
                            }}
                          />
                        )}
                      </div>
                      {repo.description && (
                        <p className="text-xs text-[var(--muted)] mt-0.5 truncate">
                          {repo.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                    <div className="flex items-center gap-1 text-xs text-[var(--muted)]">
                      <Star size={12} />
                      {repo.stars}
                    </div>
                    <RepoMetric
                      value={repo.total_issues}
                      label="open"
                      color="#58a6ff"
                    />
                    <RepoMetric
                      value={repo.good_first_issues}
                      label="gfi"
                      color="#3fb950"
                    />
                    <RepoMetric
                      value={repo.help_wanted_issues}
                      label="hw"
                      color="#e3b341"
                    />
                  </div>
                </button>

                {expandedRepo === repo.id && (
                  <div className="border-t border-[var(--border)]">
                    {(detailLoading || contribLoading) ? (
                      <div className="p-8 text-center text-sm text-[var(--muted)]">
                        Loading details...
                      </div>
                    ) : (
                      <div className="p-4 space-y-6">
                        <div>
                          <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
                            Open Issues ({(repoDetail as MaintainerRepoDetail)?.issues?.length ?? 0})
                          </h3>
                          {(repoDetail as MaintainerRepoDetail)?.issues?.length === 0 && (
                            <p className="text-sm text-[var(--muted)]">
                              No open issues indexed for this repo.
                            </p>
                          )}
                          <div className="space-y-2">
                            {(repoDetail as MaintainerRepoDetail)?.issues?.map((issue) => (
                              <a
                                key={issue.id}
                                href={issue.html_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)] border border-[var(--border)] hover:border-[var(--border-bright)] transition-colors group"
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <MessageSquare
                                    size={12}
                                    className="text-[var(--muted)] flex-shrink-0"
                                  />
                                  <span className="text-sm text-[var(--foreground)] truncate group-hover:text-[var(--accent)] transition-colors">
                                    {issue.title}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                                  {issue.is_good_first_issue && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(63,185,80,0.12)] text-[#3fb950] font-medium">
                                      GFI
                                    </span>
                                  )}
                                  {issue.is_help_wanted && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[rgba(88,166,255,0.12)] text-[#58a6ff] font-medium">
                                      HW
                                    </span>
                                  )}
                                  <span className="text-xs text-[var(--muted)]">
                                    #{issue.number}
                                  </span>
                                  <ExternalLink
                                    size={12}
                                    className="text-[var(--muted)] opacity-0 group-hover:opacity-100 transition-opacity"
                                  />
                                </div>
                              </a>
                            ))}
                          </div>
                        </div>

                        <div>
                          <h3 className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
                            Suggested Contributors ({(contributors as ContributorMatch[])?.length ?? 0})
                          </h3>
                          {(contributors as ContributorMatch[])?.length === 0 && (
                            <p className="text-sm text-[var(--muted)]">
                              No matching contributors found yet. Users need to
                              analyze their profiles first.
                            </p>
                          )}
                          <div className="grid gap-2 sm:grid-cols-2">
                            {(contributors as ContributorMatch[])?.map((c) => (
                              <div
                                key={c.user_id}
                                className="flex items-center gap-3 p-3 rounded-lg bg-[var(--background)] border border-[var(--border)]"
                              >
                                {c.github_avatar_url ? (
                                  <Image
                                    src={c.github_avatar_url}
                                    alt={c.github_username}
                                    width={32}
                                    height={32}
                                    className="w-8 h-8 rounded-full flex-shrink-0"
                                    unoptimized
                                  />
                                ) : (
                                  <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] flex items-center justify-center flex-shrink-0">
                                    <Users size={14} />
                                  </div>
                                )}
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-[var(--foreground)]">
                                      {c.github_username}
                                    </span>
                                    <span
                                      className="text-xs font-mono"
                                      style={{
                                        color:
                                          c.match_score >= 0.7
                                            ? "var(--accent)"
                                            : c.match_score >= 0.4
                                            ? "var(--warning)"
                                            : "var(--muted)",
                                      }}
                                    >
                                      {Math.round(c.match_score * 100)}%
                                    </span>
                                  </div>
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {c.matching_skills.slice(0, 3).map((skill) => (
                                      <span
                                        key={skill}
                                        className="skill-badge text-[10px]"
                                      >
                                        {skill}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center gap-2 mb-2" style={{ color }}>
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p className="text-2xl font-bold font-mono text-[var(--foreground)]">
        {value}
      </p>
    </div>
  );
}

function RepoMetric({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-1 text-xs" style={{ color }}>
      <span className="font-mono font-medium">{value}</span>
      <span className="text-[var(--muted)]">{label}</span>
    </div>
  );
}
