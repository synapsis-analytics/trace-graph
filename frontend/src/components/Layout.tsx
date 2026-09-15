import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Command, Moon, Network, Sun } from "lucide-react";
import { useHealth } from "@/hooks/useApi";
import { Badge, Button, Tooltip } from "./ui/primitives";
import { CommandPalette } from "./CommandPalette";
import { KeyButton, KeyDialog } from "./KeyDialog";
import { themeStore, type ThemeMode } from "@/lib/storage";
import { cn, formatNumber } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Explore", end: true },
  { to: "/path", label: "Path finder" },
  { to: "/framework", label: "Framework" },
  { to: "/coverage", label: "Coverage" },
  { to: "/registry", label: "Registry" },
  { to: "/ask", label: "Ask" },
  { to: "/api-guide", label: "API & MCP" },
];

const ENV_STYLES: Record<string, string> = {
  prod: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  production: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  test: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300",
  staging: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300",
  dev: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  mock: "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-500/15 dark:text-fuchsia-300",
};

export function Layout() {
  const { data: health } = useHealth();
  const [theme, setTheme] = useState<ThemeMode>(() => themeStore.get());
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    themeStore.apply(theme);
    themeStore.set(theme);
  }, [theme]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const env = health?.env ?? "…";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="z-20 flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface px-3 py-2">
        <NavLink to="/" className="flex items-center gap-2">
          <Network className="h-5 w-5 text-brand" />
          <span className="text-sm font-semibold tracking-tight">TRACE Graph</span>
        </NavLink>
        <Badge className={cn("uppercase", ENV_STYLES[env] ?? "bg-slate-100 text-slate-700")} title={`Environment reported by /health — version ${health?.version ?? "?"}`}>
          {env}
        </Badge>

        <nav className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                  isActive ? "bg-bg text-ink" : "text-muted hover:bg-bg hover:text-ink",
                )
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-muted lg:inline">
            {formatNumber(health?.objects)} objects · {formatNumber(health?.links)} links · {formatNumber(health?.claims)} claims
          </span>
          <Tooltip label="Search (⌘K)">
            <Button size="sm" variant="ghost" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">
              <Command className="h-4 w-4" />
              <span className="kbd hidden lg:inline">⌘K</span>
            </Button>
          </Tooltip>
          <KeyButton onOpen={() => setKeyOpen(true)} />
          <Button
            size="icon"
            variant="ghost"
            aria-label="Toggle dark mode"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <main className="relative min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>

      <footer className="shrink-0 border-t border-line bg-surface px-3 py-1.5 text-[11px] text-muted">
        TRACE prototype — public data — assumptions, not decisions.
        {health?.taxonomy?.version ? <> Taxonomy {health.taxonomy.version}{health.taxonomy.reachable === false ? " (service unreachable)" : ""}.</> : null}
      </footer>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onPick={(id) => navigate(`/?focus=${encodeURIComponent(id)}`)} />
      <KeyDialog open={keyOpen} onClose={() => setKeyOpen(false)} />
    </div>
  );
}
