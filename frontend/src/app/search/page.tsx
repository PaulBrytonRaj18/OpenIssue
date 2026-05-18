"use client";
import { Suspense, useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search as SearchIcon, Filter, X, SlidersHorizontal, Bookmark, Sparkles } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { IssueCard } from "@/components/IssueCard";
import { EmptyState } from "@/components/EmptyState";
import { PageLoader } from "@/components/Spinner";
import { useSmartSearch, useSearch } from "@/lib/hooks/use-issues";
import { useSuggestions, useSaveSearch } from "@/lib/hooks/use-searches";
import { MatchedIssue, SmartSearchResult, SuggestionItem } from "@/lib/types";

const LANGUAGES = ["", "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "Ruby", "PHP", "C++", "Swift", "Kotlin"];
const DIFFICULTIES = [
  { value: "", label: "Any Difficulty" },
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
];
const LABEL_FILTERS = [
  { value: "", label: "Any Label" },
  { value: "good_first", label: "Good First Issue" },
  { value: "help_wanted", label: "Help Wanted" },
];

export default function SearchPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading search..." />}>
      <SearchPageContent />
    </Suspense>
  );
}

function SearchPageContent() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [language, setLanguage] = useState(searchParams.get("language") || "");
  const [difficulty, setDifficulty] = useState(searchParams.get("difficulty") || "");
  const [labelFilter, setLabelFilter] = useState(searchParams.get("label") || "");
  const [searched, setSearched] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [useSmartSearchBool, setUseSmartSearchBool] = useState(true);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suggestionRef = useRef<HTMLDivElement>(null);

  const saveSearchMutation = useSaveSearch();

  const searchParamsRecord = useMemo(() => {
    if (!query.trim()) return null;
    const params: Record<string, string | number> = { q: query.trim(), limit: 30 };
    if (language) params.language = language;
    if (difficulty) params.difficulty = difficulty;
    if (labelFilter) params.label = labelFilter;
    return params;
  }, [query, language, difficulty, labelFilter]);

  const searchQuery = useMemo(() => {
    if (!searchParamsRecord) return null;
    if (useSmartSearchBool) {
      return {
        q: searchParamsRecord.q as string,
        language: searchParamsRecord.language as string | undefined,
        difficulty: searchParamsRecord.difficulty as string | undefined,
        label: searchParamsRecord.label as string | undefined,
        limit: searchParamsRecord.limit as number | undefined,
      };
    }
    return searchParamsRecord as {
      q: string;
      language?: string;
      difficulty?: string;
      label?: string;
      limit?: number;
    };
  }, [searchParamsRecord, useSmartSearchBool]);

  const smartSearchResult = useSmartSearch(
    useSmartSearchBool && searchQuery ? searchQuery as Parameters<typeof useSmartSearch>[0] : null
  );
  const regularSearchResult = useSearch(
    !useSmartSearchBool && searchQuery ? searchQuery as Parameters<typeof useSearch>[0] : null
  );

  const results = useSmartSearchBool ? smartSearchResult.data : regularSearchResult.data;
  const isLoading = useSmartSearchBool ? smartSearchResult.isLoading : regularSearchResult.isLoading;

  const suggestionsQuery = useSuggestions(debouncedQuery);

  useEffect(() => {
    if (suggestionsQuery.data?.suggestions) {
      setShowSuggestions(suggestionsQuery.data.suggestions.length > 0);
    }
  }, [suggestionsQuery.data]);

  const performSearch = useCallback(() => {
    if (!query.trim()) return;
    setSearched(true);
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (language) params.set("language", language);
    if (difficulty) params.set("difficulty", difficulty);
    if (labelFilter) params.set("label", labelFilter);
    router.replace(`/search?${params.toString()}`, { scroll: false });
    setShowSuggestions(false);
  }, [query, language, difficulty, labelFilter, router]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") performSearch();
  }, [performSearch]);

  const clearSearch = useCallback(() => {
    setQuery("");
    setSearched(false);
    setDebouncedQuery("");
    inputRef.current?.focus();
    router.replace("/search", { scroll: false });
  }, [router]);

  const onQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQuery(val), 300);
  }, []);

  const selectSuggestion = useCallback((item: SuggestionItem) => {
    setQuery(item.text);
    setShowSuggestions(false);
    if (item.type === "language") {
      setLanguage(item.text);
    }
  }, []);

  const saveSearch = useCallback(async () => {
    if (!saveName.trim()) return;
    try {
      await saveSearchMutation.mutateAsync({
        name: saveName.trim(),
        query: query,
        filters: { language, difficulty, label: labelFilter },
      });
      setShowSaveDialog(false);
      setSaveName("");
    } catch {
      /* ignore */
    }
  }, [saveName, query, language, difficulty, labelFilter, saveSearchMutation]);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
    }
  }, [status, router]);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !searched) {
      setQuery(q);
      setSearched(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (suggestionRef.current && !suggestionRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  if (status === "loading") return <PageLoader message="Loading..." />;

  const matches = results?.matches ?? [];
  const smartResult = results as SmartSearchResult | null;
  const isSmart = useSmartSearchBool && smartResult?.intent;

  return (
    <>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold text-[var(--foreground)] mb-1">
            Search Issues
          </h1>
          <p className="text-sm text-[var(--muted)]">
            Find open-source issues by keyword, language, and difficulty.
          </p>
        </div>

        <div className="flex items-center gap-2 mb-4">
          <div className="flex-1 relative">
            <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={onQueryChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (suggestionsQuery.data?.suggestions?.length > 0) setShowSuggestions(true);
              }}
              placeholder='e.g. "beginner React issues" or "FastAPI backend bugs"'
              className="w-full pl-10 pr-10 py-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] text-sm placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent-dim)] transition-colors"
            />
            {query && (
              <button onClick={clearSearch} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
                <X size={16} />
              </button>
            )}

            {showSuggestions && suggestionsQuery.data?.suggestions && (
              <div ref={suggestionRef} className="absolute top-full left-0 right-0 mt-1 z-50 rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-lg overflow-hidden animate-fade-in">
                {suggestionsQuery.data.suggestions.map((s: SuggestionItem, i: number) => (
                  <button
                    key={i}
                    onClick={() => selectSuggestion(s)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-[var(--accent-dim)] transition-colors"
                  >
                    {s.type === "language" ? (
                      <SearchIcon size={14} className="text-[var(--muted)]" />
                    ) : (
                      <SearchIcon size={14} className="text-[var(--muted)]" />
                    )}
                    <span className="text-[var(--foreground)] font-medium">{s.text}</span>
                    {s.description && (
                      <span className="text-[var(--muted)] text-xs ml-auto">{s.description}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={performSearch}
            disabled={isLoading || !query.trim()}
            className="px-5 py-3 rounded-xl bg-[var(--accent)] text-black text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isLoading ? "Searching..." : "Search"}
          </button>

          <button
            onClick={() => setUseSmartSearchBool(!useSmartSearchBool)}
            className={`p-3 rounded-xl border transition-colors ${
              useSmartSearchBool
                ? "border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-dim)]"
                : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
            title={useSmartSearchBool ? "Smart search enabled" : "Toggle smart search"}
          >
            <Sparkles size={16} />
          </button>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-3 rounded-xl border transition-colors ${
              showFilters
                ? "border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-dim)]"
                : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
            title="Toggle filters"
          >
            <SlidersHorizontal size={16} />
          </button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap items-center gap-3 mb-6 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] animate-fade-in">
            <Filter size={14} className="text-[var(--muted)]" />
            <select value={language} onChange={(e) => setLanguage(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-xs border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:border-[var(--border-bright)]">
              <option value="">All Languages</option>
              {LANGUAGES.filter(Boolean).map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-xs border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:border-[var(--border-bright)]">
              {DIFFICULTIES.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
            <select value={labelFilter} onChange={(e) => setLabelFilter(e.target.value)}
              className="px-3 py-1.5 rounded-lg text-xs border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:border-[var(--border-bright)]">
              {LABEL_FILTERS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>
        )}

        {!isLoading && searched && isSmart && (
          <div className="flex items-center gap-2 mb-4 text-xs text-[var(--muted)]">
            <Sparkles size={12} className="text-[var(--accent)]" />
            <span>Smart search</span>
            {smartResult?.intent?.languages && smartResult.intent.languages.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-[var(--accent-dim)] text-[var(--accent)]">
                {smartResult.intent.languages.join(", ")}
              </span>
            )}
            {smartResult?.intent?.difficulty && (
              <span className="px-2 py-0.5 rounded-full bg-[var(--accent-dim)] text-[var(--accent)]">
                {smartResult.intent.difficulty}
              </span>
            )}
            {smartResult?.intent?.labels?.map((l: string) => (
              <span key={l} className="px-2 py-0.5 rounded-full bg-[var(--accent-dim)] text-[var(--accent)]">
                {l.replace("_", " ")}
              </span>
            ))}
            {smartResult?.personalized && (
              <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">
                personalized
              </span>
            )}
            <button
              onClick={() => setShowSaveDialog(true)}
              className="ml-auto px-2.5 py-1 rounded-lg border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-bright)] flex items-center gap-1"
            >
              <Bookmark size={12} />
              Save
            </button>
          </div>
        )}

        {showSaveDialog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-[var(--surface)] rounded-xl p-6 w-96 border border-[var(--border)] shadow-xl">
              <h3 className="font-display font-bold text-[var(--foreground)] mb-3">Save Search</h3>
              <input
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="e.g. Daily React beginner issues"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm mb-4 focus:outline-none focus:border-[var(--accent)]"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && saveSearch()}
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowSaveDialog(false)}
                  className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
                  Cancel
                </button>
                <button onClick={saveSearch}
                  disabled={!saveName.trim() || saveSearchMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-[var(--accent)] text-black text-sm font-semibold hover:opacity-90 disabled:opacity-50">
                  Save
                </button>
              </div>
            </div>
          </div>
        )}

        {isLoading && <PageLoader message="Searching issues..." />}

        {!isLoading && searched && matches.length === 0 && (
          <EmptyState
            icon={<SearchIcon size={22} />}
            title="No issues found"
            description={`No results for "${query}". Try different keywords or fewer filters.`}
            action={
              <button onClick={() => { setDifficulty(""); setLabelFilter(""); setLanguage(""); }}
                className="px-4 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--muted)] hover:text-[var(--foreground)]">
                Clear Filters
              </button>
            }
          />
        )}

        {!isLoading && searched && matches.length > 0 && (
          <div>
            <p className="text-xs text-[var(--muted)] mb-4 font-mono">
              {results?.total ?? matches.length} result{matches.length !== 1 ? "s" : ""} for &ldquo;{query}&rdquo;
            </p>
            <div className="space-y-4">
              {matches.map((match: MatchedIssue, i: number) => (
                <IssueCard key={`${match.issue.id}-${i}`} match={match} index={i} />
              ))}
            </div>
          </div>
        )}

        {!isLoading && !searched && (
          <div className="py-20 text-center">
            <SearchIcon size={32} className="mx-auto mb-4 text-[var(--muted)]" />
            <h3 className="font-display font-bold text-[var(--foreground)] text-lg mb-2">
              Search Open Source Issues
            </h3>
            <p className="text-sm text-[var(--muted)] max-w-md mx-auto">
              Type a query like &ldquo;beginner React issues&rdquo; or &ldquo;FastAPI performance bugs&rdquo; and press Enter.
              Toggle <Sparkles size={12} className="inline" /> for smart search with auto-detected intent.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
