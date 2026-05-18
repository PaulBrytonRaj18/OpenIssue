"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { TrendingUp, Flame, RefreshCw } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { IssueCard } from "@/components/IssueCard";
import { EmptyState } from "@/components/EmptyState";
import { PageLoader } from "@/components/Spinner";
import { useTrending } from "@/lib/hooks/use-issues";
import type { MatchedIssue } from "@/lib/types";

const LANGUAGES = ["All", "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java"];

export default function TrendingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [language, setLanguage] = useState("All");

  const trendingParams = {
    ...(language !== "All" && { language }),
    limit: 30,
  };

  const {
    data: trendingData,
    isLoading,
    refetch,
  } = useTrending(trendingParams);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <>
        <Navbar />
        <PageLoader />
      </>
    );
  }

  const matches = trendingData?.matches ?? [];

  return (
    <>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Flame size={22} className="text-[var(--accent)]" />
              <h1 className="font-display text-2xl font-bold text-[var(--foreground)]">
                Trending Issues
              </h1>
            </div>
            <p className="text-sm text-[var(--muted)]">
              Popular good-first-issues from active repositories across GitHub.
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors disabled:opacity-50"
          >
            <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        <div className="flex items-center gap-2 mb-6">
          <TrendingUp size={13} className="text-[var(--muted)]" />
          <div className="flex items-center gap-1 flex-wrap">
            {LANGUAGES.map((lang) => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
                  language === lang
                    ? "bg-[var(--accent-dim)] text-[var(--accent)] border border-[var(--accent-dim)]"
                    : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                }`}
              >
                {lang}
              </button>
            ))}
          </div>
        </div>

        {isLoading && <PageLoader message="Fetching trending issues..." />}

        {!isLoading && matches.length === 0 && (
          <EmptyState
            icon={<Flame size={22} />}
            title="No trending issues"
            description="No trending issues found for this language right now. Try another language or check back later."
          />
        )}

        {!isLoading && matches.length > 0 && (
          <div className="space-y-4">
            {matches.map((match: MatchedIssue, i: number) => (
              <IssueCard key={`${match.issue.id}-${i}`} match={match} index={i} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
