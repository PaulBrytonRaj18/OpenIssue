"use client";
import { useState, memo, useCallback } from "react";
import {
  MessageSquare,
  Star,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  Zap,
} from "lucide-react";
import {
  MatchedIssue,
  complexityLabel,
  complexityColor,
  timeAgo,
  LANGUAGE_COLORS,
} from "@/lib/types";
import { issuesApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

interface IssueCardProps {
  match: MatchedIssue;
  index?: number;
}

export const IssueCard = memo(function IssueCard({ match, index = 0 }: IssueCardProps) {
  const { issue, match_score, matching_skills, why_matched } = match;
  const repo = issue.repository;
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const scorePercent = Math.round(match_score * 100);
  const langColor =
    LANGUAGE_COLORS[repo?.primary_language?.toLowerCase() ?? ""] ?? "#8b949e";

  const handleSave = useCallback(async () => {
    if (saving || saved) return;
    setSaving(true);
    try {
      await issuesApi.saveIssue(issue.id);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.saved });
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  }, [saving, saved, issue.id, queryClient]);

  const scoreColor =
    scorePercent >= 70
      ? "var(--accent)"
      : scorePercent >= 40
      ? "var(--warning)"
      : "var(--muted)";

  return (
    <div
      className="group glass rounded-xl border border-[var(--border)] hover:border-[var(--border-bright)] transition-all duration-200 animate-fade-in overflow-hidden"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="match-bar rounded-none" style={{ borderRadius: 0 }}>
        <div
          className="match-bar-fill"
          style={{ width: `${scorePercent}%` }}
        />
      </div>

      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0 flex-1">
            {repo && (
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-mono text-[var(--muted)] truncate">
                  {repo.full_name}
                </span>
                <div className="flex items-center gap-1 text-[10px] text-[var(--muted)]">
                  <Star size={10} />
                  {repo.stars >= 1000
                    ? `${(repo.stars / 1000).toFixed(1)}k`
                    : repo.stars}
                </div>
              </div>
            )}
            <h3 className="text-sm font-medium text-[var(--foreground)] leading-snug line-clamp-2">
              {issue.title}
            </h3>
          </div>

          <div className="flex-shrink-0 flex flex-col items-center">
            <div
              className="text-lg font-bold font-mono"
              style={{ color: scoreColor }}
            >
              {scorePercent}%
            </div>
            <div className="text-[9px] text-[var(--muted)] font-mono">match</div>
          </div>
        </div>

        {why_matched && (
          <div className="flex items-start gap-2 mb-3 p-2.5 rounded-lg bg-[var(--accent-glow)] border border-[var(--accent-dim)]">
            <Zap size={12} className="text-[var(--accent)] flex-shrink-0 mt-0.5" />
            <p className="text-xs text-[var(--foreground-dim)] leading-snug">
              {why_matched}
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          {issue.is_good_first_issue && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: "rgba(63,185,80,0.12)", color: "#3fb950" }}
            >
              good first issue
            </span>
          )}
          {issue.is_help_wanted && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: "rgba(88,166,255,0.12)", color: "#58a6ff" }}
            >
              help wanted
            </span>
          )}
          {(issue.labels ?? [])
            .filter((l) => l !== "good first issue" && l !== "help wanted")
            .slice(0, 2)
            .map((label) => (
              <span
                key={label}
                className="text-[10px] px-2 py-0.5 rounded-full border border-[var(--border)] text-[var(--muted)]"
              >
                {label}
              </span>
            ))}
        </div>

        {matching_skills.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {matching_skills.slice(0, 5).map((skill) => (
              <span key={skill} className="skill-badge">
                {skill}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
          <div className="flex items-center gap-3 text-[var(--muted)]">
            {repo?.primary_language && (
              <div className="flex items-center gap-1 text-xs">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: langColor }}
                />
                {repo.primary_language}
              </div>
            )}
            <div className="flex items-center gap-1 text-xs">
              <MessageSquare size={11} />
              {issue.comments}
            </div>
            <div
              className="text-xs font-mono"
              style={{ color: complexityColor(issue.complexity_score) }}
            >
              {complexityLabel(issue.complexity_score)}
            </div>
            {issue.created_at && (
              <span className="text-xs hidden sm:inline">
                {timeAgo(issue.created_at)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className={`p-1.5 rounded-lg transition-colors ${
                saved
                  ? "text-[var(--accent)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)]"
              }`}
              title={saved ? "Saved" : "Save issue"}
            >
              {saved ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
            </button>
            <a
              href={issue.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--surface-2)] text-[var(--foreground-dim)] hover:text-[var(--foreground)] hover:bg-[var(--border)] transition-colors"
            >
              View Issue
              <ExternalLink size={11} />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
});
