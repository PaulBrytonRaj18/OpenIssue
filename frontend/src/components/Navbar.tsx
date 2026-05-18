"use client";
import Link from "next/link";
import Image from "next/image";
import { useState, memo, useCallback } from "react";
import { useSession, signOut } from "next-auth/react";
import { usePathname } from "next/navigation";
import { Github, LayoutDashboard, Bookmark, LogOut, User, Search, TrendingUp, Save, Shield } from "lucide-react";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard size={15} /> },
  { href: "/search", label: "Search", icon: <Search size={15} /> },
  { href: "/trending", label: "Trending", icon: <TrendingUp size={15} /> },
  { href: "/saved", label: "Saved", icon: <Bookmark size={15} /> },
  { href: "/searches", label: "Searches", icon: <Save size={15} /> },
  { href: "/maintainer", label: "Maintain", icon: <Shield size={15} /> },
  { href: "/profile", label: "Profile", icon: <User size={15} /> },
];

export const Navbar = memo(function Navbar() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const user = session?.user as { username?: string; avatarUrl?: string };

  const toggleMenu = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/90 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        <Link href="/dashboard" className="flex items-center gap-2 flex-shrink-0">
          <Image
            src="/logo.svg"
            alt="IssueCompass"
            width={36}
            height={36}
            className="w-9 h-9"
          />
          <span className="font-display font-bold text-base text-[var(--foreground)] hidden sm:inline">
            IssueCompass
          </span>
        </Link>

        <nav className="flex items-center gap-1" aria-label="Main navigation">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                pathname === link.href
                  ? "bg-[var(--accent-dim)] text-[var(--accent)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface)]"
              }`}
            >
              {link.icon}
              <span className="hidden sm:inline">{link.label}</span>
            </Link>
          ))}
        </nav>

        {session && (
          <div className="relative">
            <button
              onClick={toggleMenu}
              className="flex items-center gap-2 p-1 rounded-lg hover:bg-[var(--surface)] transition-colors"
            >
              {user?.avatarUrl ? (
                <Image
                  src={user.avatarUrl}
                  alt="avatar"
                  width={28}
                  height={28}
                  className="rounded-full"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-[var(--surface-2)] flex items-center justify-center">
                  <User size={14} />
                </div>
              )}
              <span className="text-sm text-[var(--foreground-dim)] hidden sm:inline">
                {user?.username}
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-44 glass rounded-xl shadow-xl border border-[var(--border)] overflow-hidden">
                <a
                  href={`https://github.com/${user?.username}`}
                  target="_blank"
                  className="flex items-center gap-2 px-4 py-3 text-sm text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-2)] transition-colors"
                >
                  <Github size={14} />
                  GitHub Profile
                </a>
                <button
                  onClick={() => signOut({ callbackUrl: "/" })}
                  className="w-full flex items-center gap-2 px-4 py-3 text-sm text-[var(--danger)] hover:bg-[var(--surface-2)] transition-colors"
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
});
