"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Search, Trash2, Bell, BellOff, ExternalLink, RefreshCw } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { EmptyState } from "@/components/EmptyState";
import { PageLoader } from "@/components/Spinner";
import { searchesApi } from "@/lib/api";
import { SavedSearch } from "@/lib/types";

export default function SavedSearchesPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSearches = async () => {
    setLoading(true);
    try {
      const res = await searchesApi.listSearches();
      setSearches(res.data);
    } catch {
      setSearches([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (status === "authenticated") fetchSearches();
  }, [status]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("issuecompass_token");
      if (!token && status === "unauthenticated") {
        router.push("/");
      }
    }
  }, [status, router]);

  const handleDelete = async (id: number) => {
    try {
      await searchesApi.deleteSearch(id);
      setSearches((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // ignore
    }
  };

  const handleToggleNotify = async (s: SavedSearch) => {
    try {
      const res = await searchesApi.updateSearch(s.id, { notify: !s.notify });
      setSearches((prev) => prev.map((item) => (item.id === s.id ? res.data : item)));
    } catch {
      // ignore
    }
  };

  const handleCheck = async (id: number) => {
    try {
      const res = await searchesApi.checkSearch(id);
      const data = res.data;
      if (data.new_since_last_check > 0) {
        alert(`${data.new_since_last_check} new issue${data.new_since_last_check > 1 ? "s" : ""} found!`);
      } else {
        alert("No new issues since last check.");
      }
    } catch {
      // ignore
    }
  };

  if (status === "loading") return <PageLoader message="Loading..." />;

  return (
    <>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold text-[var(--foreground)] mb-1">
            Saved Searches
          </h1>
          <p className="text-sm text-[var(--muted)]">
            Your saved search queries. Check for new matching issues anytime.
          </p>
        </div>

        {loading && <PageLoader message="Loading saved searches..." />}

        {!loading && searches.length === 0 && (
          <EmptyState
            icon={<Search size={22} />}
            title="No saved searches"
            description="Run a search on the Search page and save it to track new issues."
            action={
              <button
                onClick={() => router.push("/search")}
                className="px-4 py-2 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold"
              >
                Go to Search
              </button>
            }
          />
        )}

        {!loading && searches.length > 0 && (
          <div className="space-y-3">
            {searches.map((s) => (
              <div
                key={s.id}
                className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] flex items-center gap-4"
              >
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-[var(--foreground)] text-sm truncate">
                    {s.name}
                  </h3>
                  <p className="text-xs text-[var(--muted)] font-mono truncate mt-0.5">
                    {s.query}
                  </p>
                  <p className="text-xs text-[var(--muted)] mt-1">
                    Saved {new Date(s.created_at).toLocaleDateString()}
                    {s.last_checked_at && ` · Last checked ${new Date(s.last_checked_at).toLocaleDateString()}`}
                  </p>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleCheck(s.id)}
                    className="p-2 rounded-lg border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors"
                    title="Check for new issues"
                  >
                    <RefreshCw size={14} />
                  </button>

                  <button
                    onClick={() => router.push(`/search?q=${encodeURIComponent(s.query)}`)}
                    className="p-2 rounded-lg border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] transition-colors"
                    title="Run search"
                  >
                    <ExternalLink size={14} />
                  </button>

                  <button
                    onClick={() => handleToggleNotify(s)}
                    className={`p-2 rounded-lg border transition-colors ${
                      s.notify
                        ? "border-[var(--accent)] text-[var(--accent)]"
                        : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                    title={s.notify ? "Notifications on" : "Notifications off"}
                  >
                    {s.notify ? <Bell size={14} /> : <BellOff size={14} />}
                  </button>

                  <button
                    onClick={() => handleDelete(s.id)}
                    className="p-2 rounded-lg border border-[var(--border)] text-[var(--muted)] hover:text-red-400 hover:border-red-400/30 transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
