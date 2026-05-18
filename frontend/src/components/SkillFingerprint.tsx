"use client";
import { memo, useMemo } from "react";
import { SkillFingerprint, LANGUAGE_COLORS } from "@/lib/types";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Code2, Layers, TrendingUp, Star, GitBranch } from "lucide-react";

interface Props {
  fingerprint: SkillFingerprint;
}

const CATEGORY_LABELS: Record<string, string> = {
  frontend: "Frontend",
  backend: "Backend",
  database: "Database",
  devops: "DevOps",
  ai_ml: "AI / ML",
  mobile: "Mobile",
  systems: "Systems",
};

const EXPERIENCE_CONFIG = {
  beginner: { label: "Beginner", color: "#3fb950", width: "25%" },
  intermediate: { label: "Intermediate", color: "#e3b341", width: "60%" },
  advanced: { label: "Advanced", color: "#00d4aa", width: "90%" },
};

export const SkillFingerprintPanel = memo(function SkillFingerprintPanel({ fingerprint }: Props) {
  const {
    languages,
    categories,
    top_skills,
    experience_level,
    total_repos,
    total_stars_received,
  } = fingerprint;

  const radarData = useMemo(
    () =>
      Object.entries(CATEGORY_LABELS)
        .map(([key, label]) => ({
          category: label,
          score: categories[key] ? Math.min(categories[key].length * 20, 100) : 0,
        }))
        .filter((d) => d.score > 0),
    [categories]
  );

  const topLangs = useMemo(
    () =>
      Object.entries(languages)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6),
    [languages]
  );

  const expConfig =
    EXPERIENCE_CONFIG[experience_level] ?? EXPERIENCE_CONFIG.intermediate;

  const stats = useMemo(
    () => [
      { icon: <GitBranch size={14} />, label: "Repos", value: total_repos },
      {
        icon: <Star size={14} />,
        label: "Stars",
        value:
          total_stars_received >= 1000
            ? `${(total_stars_received / 1000).toFixed(1)}k`
            : total_stars_received,
      },
      {
        icon: <Code2 size={14} />,
        label: "Skills",
        value: top_skills.length,
      },
    ],
    [total_repos, total_stars_received, top_skills.length]
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center p-3 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]"
          >
            <div className="text-[var(--muted)] mb-1">{stat.icon}</div>
            <div className="text-lg font-bold font-mono text-[var(--accent)]">
              {stat.value}
            </div>
            <div className="text-[10px] text-[var(--muted)]">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-[var(--muted)] font-mono">
            Experience Level
          </span>
          <span
            className="text-xs font-semibold"
            style={{ color: expConfig.color }}
          >
            {expConfig.label}
          </span>
        </div>
        <div className="match-bar">
          <div
            className="match-bar-fill"
            style={{
              width: expConfig.width,
              background: expConfig.color,
            }}
          />
        </div>
      </div>

      <div className="p-4 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
        <div className="flex items-center gap-2 mb-3">
          <Layers size={13} className="text-[var(--muted)]" />
          <span className="text-xs font-mono text-[var(--muted)]">Languages</span>
        </div>
        <div className="space-y-2.5">
          {topLangs.map(([lang, score]) => {
            const color =
              LANGUAGE_COLORS[lang.toLowerCase()] ?? "var(--accent)";
            return (
              <div key={lang}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-[var(--foreground-dim)] capitalize">
                    {lang}
                  </span>
                  <span className="text-[10px] font-mono text-[var(--muted)]">
                    {Math.round(score * 100)}%
                  </span>
                </div>
                <div className="match-bar">
                  <div
                    className="match-bar-fill"
                    style={{ width: `${score * 100}%`, background: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {radarData.length >= 3 && (
        <div className="p-4 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={13} className="text-[var(--muted)]" />
            <span className="text-xs font-mono text-[var(--muted)]">
              Skill Distribution
            </span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="category"
                tick={{ fill: "var(--muted)", fontSize: 10 }}
              />
              <Radar
                dataKey="score"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.15}
                strokeWidth={1.5}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--foreground)",
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="p-4 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]">
        <div className="flex items-center gap-2 mb-3">
          <Code2 size={13} className="text-[var(--muted)]" />
          <span className="text-xs font-mono text-[var(--muted)]">Top Skills</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {top_skills.map((skill) => (
            <span key={skill} className="skill-badge">
              {skill}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
});
