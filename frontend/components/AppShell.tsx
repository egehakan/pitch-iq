"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { LogOut } from "lucide-react";
import { useMe } from "@/lib/queries";
import { cn } from "@/lib/utils";

function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
        <rect x="1.5" y="1.5" width="21" height="21" rx="5" stroke="var(--accent)" strokeWidth="1.5" />
        <circle cx="12" cy="12" r="3.4" stroke="var(--accent)" strokeWidth="1.5" />
        <path d="M12 1.5v4.1M12 18.4v4.1" stroke="var(--accent)" strokeWidth="1.5" />
      </svg>
      <span className="font-display text-[15px] font-bold tracking-tight text-text">
        Pitch <span className="text-accent">IQ</span>
      </span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isError, isLoading } = useMe();

  useEffect(() => {
    if (isError) router.replace("/login");
  }, [isError, router]);

  const logout = async () => {
    await fetch("/api/session", { method: "DELETE" });
    router.replace("/login");
  };

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center text-sm text-faint">Loading</div>;
  }
  if (!user) return null;

  const nav = [
    { href: "/", label: "Dashboard" },
    { href: "/tournament/world-cup-2026", label: "Companion" },
  ];

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-5">
        <div className="flex items-center gap-7">
          <Wordmark />
          <nav className="hidden items-center gap-1 md:flex">
            {nav.map((n) => {
              const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 text-[13px] transition-colors",
                    active ? "text-text" : "text-muted hover:text-text",
                  )}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-[13px] text-muted sm:inline">{user.display_name}</span>
          <button
            onClick={logout}
            className="flex h-8 items-center gap-1.5 rounded-md px-2 text-[13px] text-muted transition-colors hover:bg-surface-2 hover:text-text"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
