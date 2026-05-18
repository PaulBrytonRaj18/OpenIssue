"use client";
import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Github, Zap, Target, BarChart3, ArrowRight, Star, GitFork } from "lucide-react";

const DEMO_MATCHES = [
  {
    repo: "vercel/next.js",
    title: "Add TypeScript support for new config option",
    label: "good first issue",
    lang: "TypeScript",
    stars: "120k",
    score: 94,
  },
  {
    repo: "fastapi/fastapi",
    title: "Improve error message for invalid dependency injection",
    label: "help wanted",
    lang: "Python",
    stars: "73k",
    score: 88,
  },
  {
    repo: "tailwindlabs/tailwindcss",
    title: "Document new container query utilities",
    label: "good first issue",
    lang: "CSS",
    stars: "81k",
    score: 81,
  },
];

const FEATURES = [
  {
    icon: <Zap size={20} />,
    title: "Skill Fingerprint",
    desc: "We analyze your real GitHub repos, commits, and languages — not what you claim to know.",
  },
  {
    icon: <Target size={20} />,
    title: "Vector Matching",
    desc: "pgvector semantic search finds issues where your exact skill set is the right fit.",
  },
  {
    icon: <BarChart3 size={20} />,
    title: "Live Feed",
    desc: "Your personalized issue feed updates daily. New matches every morning.",
  },
];

export default function LandingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (session) router.push("/dashboard");
  }, [session, router]);

  const handleSignIn = async () => {
    setLoading(true);
    await signIn("github", { callbackUrl: "/dashboard" });
  };

  return (
    <div className="min-h-screen grid-bg relative overflow-hidden">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[var(--accent)] opacity-[0.03] blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-blue-500 opacity-[0.03] blur-[100px]" />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <span className="text-black font-bold text-xs font-mono">OI</span>
          </div>
          <span className="font-display font-bold text-lg text-[var(--foreground)]">
            IssueCompass
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-[var(--accent-dim)] text-[var(--accent)] ml-1">
            FOSS
          </span>
        </div>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/Paul-Bryton-Raj/IssueCompass"
            target="_blank"
            className="flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <Github size={15} />
            <span className="hidden sm:inline">GitHub</span>
          </a>
          <button
            onClick={handleSignIn}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            <Github size={15} />
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </div>
      </nav>

      {/* Hero */}
      <main className="relative z-10 max-w-5xl mx-auto px-6 pt-20 pb-32">
        {/* Badge */}
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--muted)]">
            <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
            Free & Open Source — MIT License
          </div>
        </div>

        {/* Headline */}
        <div className="text-center mb-6">
          <h1 className="font-display text-5xl sm:text-7xl font-bold text-[var(--foreground)] leading-[1.1] tracking-tight mb-6">
            Stop searching.
            <br />
            <span className="text-[var(--accent)] text-glow">Start contributing.</span>
          </h1>
          <p className="text-lg sm:text-xl text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            IssueCompass analyzes your GitHub activity, builds your personal skill
            fingerprint, and matches you to open-source issues you can{" "}
            <em>actually</em> solve.
          </p>
        </div>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-20">
          <button
            onClick={handleSignIn}
            disabled={loading}
            className="group flex items-center gap-3 px-8 py-4 rounded-xl bg-[var(--accent)] text-black font-semibold text-base hover:opacity-95 active:scale-98 transition-all glow-accent disabled:opacity-60"
          >
            <Github size={18} />
            {loading ? "Connecting to GitHub..." : "Connect your GitHub — it's free"}
            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
          </button>
          <a
            href="https://github.com/Paul-Bryton-Raj/IssueCompass"
            className="flex items-center gap-2 px-6 py-4 rounded-xl border border-[var(--border)] text-[var(--foreground-dim)] text-sm hover:border-[var(--border-bright)] transition-colors"
          >
            <Star size={15} />
            Star on GitHub
          </a>
        </div>

        {/* Demo card */}
        <div className="glass rounded-2xl overflow-hidden mb-20">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--danger)]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--warning)]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[var(--success)]" />
            <span className="ml-2 text-xs font-mono text-[var(--muted)]">
              matched issues for @yourusername
            </span>
          </div>
          <div className="p-4 space-y-3">
            {DEMO_MATCHES.map((m, i) => (
              <div
                key={i}
                className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] carousel-card"
                style={{ animationDelay: `${i * 3}s` }}
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <p className="text-xs font-mono text-[var(--muted)] mb-1">
                      {m.repo}
                    </p>
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {m.title}
                    </p>
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <div className="text-xs font-mono text-[var(--accent)] font-bold">
                      {m.score}%
                    </div>
                    <div className="text-[10px] text-[var(--muted)]">match</div>
                  </div>
                </div>
                <div className="match-bar">
                  <div
                    className="match-bar-fill"
                    style={{ width: `${m.score}%` }}
                  />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="skill-badge">{m.lang}</span>
                  <span className="text-[10px] text-[var(--muted)] font-mono">
                    ⭐ {m.stars}
                  </span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full"
                    style={{
                      background: "rgba(63,185,80,0.1)",
                      color: "var(--success)",
                    }}
                  >
                    {m.label}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Features */}
        <div className="grid sm:grid-cols-3 gap-4 mb-20">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="p-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-bright)] transition-colors"
            >
              <div className="w-9 h-9 rounded-lg bg-[var(--accent-dim)] text-[var(--accent)] flex items-center justify-center mb-4">
                {f.icon}
              </div>
              <h3 className="font-display font-bold text-[var(--foreground)] mb-2">
                {f.title}
              </h3>
              <p className="text-sm text-[var(--muted)] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="text-center border border-[var(--border)] rounded-2xl p-10 bg-[var(--surface)]">
          <h2 className="font-display text-3xl font-bold text-[var(--foreground)] mb-3">
            Ready to find your next contribution?
          </h2>
          <p className="text-[var(--muted)] mb-6">
            100% free. No credit card. No email required. Just GitHub.
          </p>
          <button
            onClick={handleSignIn}
            disabled={loading}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-[var(--accent)] text-black font-semibold hover:opacity-95 transition-opacity"
          >
            <Github size={18} />
            Get your matches in 30 seconds
          </button>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-[var(--border)] py-6 text-center text-sm text-[var(--muted)]">
        <p>
          Built with ❤️ for the open source community.{" "}
          <a
            href="https://github.com/Paul-Bryton-Raj/IssueCompass"
            className="text-[var(--accent)] hover:opacity-80"
          >
            MIT License
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
