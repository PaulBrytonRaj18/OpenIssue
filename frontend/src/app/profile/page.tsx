"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  Github,
  MapPin,
  Link as LinkIcon,
  Users,
  GitBranch,
  RefreshCw,
  Star,
  Calendar,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { SkillFingerprintPanel } from "@/components/SkillFingerprint";
import { PageLoader } from "@/components/Spinner";
import { githubApi, authApi } from "@/lib/api";
import { SkillFingerprint } from "@/lib/types";

export default function ProfilePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [fingerprint, setFingerprint] = useState<SkillFingerprint | null>(null);
  const [githubProfile, setGithubProfile] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

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

  useEffect(() => {
    if (status === "unauthenticated") { router.push("/"); return; }
    if (status !== "authenticated" || !user?.username) return;

    const load = async () => {
      setLoading(true);
      try {
        // Ensure backend has user
        const authRes = await authApi.githubCallback({
          github_id: user.githubId!,
          github_username: user.username!,
          github_avatar_url: user.avatarUrl,
          github_name: user.name ?? undefined,
          email: user.email ?? undefined,
          public_repos: user.publicRepos ?? 0,
          followers: user.followers ?? 0,
        });
        if (authRes.data?.access_token) {
          localStorage.setItem("issuecompass_token", authRes.data.access_token);
        }
        // Load fingerprint and GitHub profile in parallel
        const [fpRes, ghRes] = await Promise.allSettled([
          githubApi.getFingerprint(),
          githubApi.getGitHubUser(user.username!),
        ]);
        if (fpRes.status === "fulfilled") setFingerprint(fpRes.value.data);
        if (ghRes.status === "fulfilled") setGithubProfile(ghRes.value.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const handleReanalyze = async () => {
    if (!user?.username) return;
    setAnalyzing(true);
    try {
      const res = await githubApi.analyzeProfile(user.username);
      if (res.data?.skill_json) setFingerprint(res.data.skill_json);
    } finally {
      setAnalyzing(false);
    }
  };

  if (status === "loading" || loading) {
    return <><Navbar /><PageLoader message="Loading your profile..." /></>;
  }

  const gh = githubProfile ?? {};

  return (
    <>
      <Navbar />
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex gap-8 items-start">

          {/* ── Left: GitHub Identity ───────────────────── */}
          <div className="w-72 flex-shrink-0 space-y-4">
            {/* Avatar + name */}
            <div className="p-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] flex flex-col items-center text-center">
              {user?.avatarUrl ? (
                <Image
                  src={user.avatarUrl}
                  alt="avatar"
                  width={80}
                  height={80}
                  className="rounded-full mb-3 ring-2 ring-[var(--accent)] ring-offset-2 ring-offset-[var(--surface)]"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-[var(--surface-2)] mb-3" />
              )}
              <h2 className="font-display font-bold text-lg text-[var(--foreground)]">
                {(gh.name as string) || user?.name || user?.username}
              </h2>
              <p className="text-sm font-mono text-[var(--muted)] mb-3">
                @{user?.username}
              </p>
              {(gh.bio as string) && (
                <p className="text-xs text-[var(--muted)] leading-relaxed mb-3">
                  {gh.bio as string}
                </p>
              )}
              <a
                href={`https://github.com/${user?.username}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 w-full justify-center px-4 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors"
              >
                <Github size={13} />
                View GitHub Profile
              </a>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: <GitBranch size={14} />, label: "Repos", value: (gh.public_repos as number) ?? user?.publicRepos ?? 0 },
                { icon: <Users size={14} />, label: "Followers", value: (gh.followers as number) ?? user?.followers ?? 0 },
                { icon: <Users size={14} />, label: "Following", value: (gh.following as number) ?? 0 },
                { icon: <Star size={14} />, label: "Gists", value: (gh.public_gists as number) ?? 0 },
              ].map((s) => (
                <div
                  key={s.label}
                  className="flex flex-col items-center p-3 rounded-xl bg-[var(--surface-2)] border border-[var(--border)]"
                >
                  <div className="text-[var(--muted)] mb-1">{s.icon}</div>
                  <div className="text-base font-bold font-mono text-[var(--accent)]">{s.value}</div>
                  <div className="text-[10px] text-[var(--muted)]">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Meta info */}
            <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-2">
              {(gh.location as string) && (
                <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
                  <MapPin size={12} />
                  {gh.location as string}
                </div>
              )}
              {(gh.blog as string) && (
                <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
                  <LinkIcon size={12} />
                  <a href={gh.blog as string} target="_blank" className="truncate hover:text-[var(--accent)]">
                    {(gh.blog as string).replace(/^https?:\/\//, "")}
                  </a>
                </div>
              )}
              {(gh.created_at as string) && (
                <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
                  <Calendar size={12} />
                  Joined {new Date(gh.created_at as string).getFullYear()}
                </div>
              )}
            </div>
          </div>

          {/* ── Right: Skill Fingerprint ─────────────────── */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="font-display text-2xl font-bold text-[var(--foreground)]">
                  Skill Fingerprint
                </h1>
                <p className="text-sm text-[var(--muted)] mt-0.5">
                  Auto-generated from your real GitHub activity
                </p>
              </div>
              <button
                onClick={handleReanalyze}
                disabled={analyzing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors disabled:opacity-50"
              >
                <RefreshCw size={12} className={analyzing ? "animate-spin" : ""} />
                {analyzing ? "Analyzing..." : "Re-analyze"}
              </button>
            </div>

            {fingerprint ? (
              <SkillFingerprintPanel fingerprint={fingerprint} />
            ) : (
              <div className="flex flex-col items-center justify-center py-24 border border-dashed border-[var(--border)] rounded-2xl">
                <p className="text-sm text-[var(--muted)] mb-4">
                  No skill fingerprint yet.
                </p>
                <button
                  onClick={handleReanalyze}
                  disabled={analyzing}
                  className="px-6 py-2.5 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold disabled:opacity-60"
                >
                  {analyzing ? "Analyzing your GitHub..." : "Generate Fingerprint"}
                </button>
              </div>
            )}

            {/* Skill categories breakdown */}
            {fingerprint?.categories && (
              <div className="mt-6 p-5 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <h3 className="text-sm font-mono text-[var(--muted)] mb-4">
                  Skill Categories Breakdown
                </h3>
                <div className="grid sm:grid-cols-2 gap-3">
                  {Object.entries(fingerprint.categories).map(([cat, skills]) => (
                    <div
                      key={cat}
                      className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]"
                    >
                      <div className="text-xs font-semibold text-[var(--foreground-dim)] capitalize mb-2">
                        {cat.replace("_", " / ")}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(skills as string[]).map((s) => (
                          <span key={s} className="skill-badge">{s}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
