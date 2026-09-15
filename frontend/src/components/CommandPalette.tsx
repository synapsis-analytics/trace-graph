/** ⌘K / Ctrl-K palette: search objects (GET /api/objects?q=) and jump to pages. */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CornerDownLeft, Search } from "lucide-react";
import { useDebounced, useObjects } from "@/hooks/useApi";
import { TypeIcon } from "./TypeBits";
import { Spinner } from "./ui/primitives";
import { typeLabel } from "@/lib/theme";
import { cn } from "@/lib/utils";

const PAGES = [
  { path: "/", label: "Explore — the network graph" },
  { path: "/path", label: "Path finder — how two things connect" },
  { path: "/framework", label: "Framework — results framework tree" },
  { path: "/coverage", label: "Coverage — taxonomy coverage and gaps" },
  { path: "/registry", label: "Registry — claims, QA and review" },
  { path: "/ask", label: "Ask — question the graph" },
  { path: "/api-guide", label: "API & MCP — the machine side" },
];

export function CommandPalette({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (id: string) => void;
}) {
  const [term, setTerm] = useState("");
  const [cursor, setCursor] = useState(0);
  const debounced = useDebounced(term, 200);
  const navigate = useNavigate();
  const { data, isFetching } = useObjects({ q: debounced, limit: 12 }, open && debounced.length > 1);

  const pages = useMemo(
    () => PAGES.filter((p) => p.label.toLowerCase().includes(term.toLowerCase())).slice(0, term ? 3 : 7),
    [term],
  );
  const objects = useMemo(() => data?.items ?? [], [data]);
  const total = pages.length + objects.length;

  useEffect(() => {
    if (!open) {
      setTerm("");
      setCursor(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setCursor((c) => (total === 0 ? 0 : (c + 1) % total));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setCursor((c) => (total === 0 ? 0 : (c - 1 + total) % total));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (cursor < pages.length) {
          const page = pages[cursor];
          if (page) navigate(page.path);
        } else {
          const o = objects[cursor - pages.length];
          if (o) onPick(o.id);
        }
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, cursor, total, pages, objects, navigate, onPick, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-slate-900/40 p-4 pt-24 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-label="Command palette"
        className="w-full max-w-xl overflow-hidden rounded-xl border border-line bg-surface shadow-soft"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 text-muted" />
          <input
            autoFocus
            value={term}
            onChange={(e) => {
              setTerm(e.target.value);
              setCursor(0);
            }}
            placeholder="Search objects or jump to a page…"
            aria-label="Search objects or jump to a page"
            className="h-11 flex-1 bg-transparent text-sm outline-none placeholder:text-muted/70"
          />
          {isFetching ? <Spinner /> : <span className="kbd">esc</span>}
        </div>
        <ul className="max-h-80 overflow-y-auto p-1">
          {pages.map((p, i) => (
            <li key={p.path}>
              <button
                type="button"
                onMouseEnter={() => setCursor(i)}
                onClick={() => {
                  navigate(p.path);
                  onClose();
                }}
                className={cn("flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm", cursor === i ? "bg-bg" : "")}
              >
                <CornerDownLeft className="h-3.5 w-3.5 text-muted" />
                <span className="flex-1 truncate">{p.label}</span>
                <span className="text-[11px] text-muted">page</span>
              </button>
            </li>
          ))}
          {objects.map((o, i) => {
            const idx = pages.length + i;
            return (
              <li key={o.id}>
                <button
                  type="button"
                  onMouseEnter={() => setCursor(idx)}
                  onClick={() => {
                    onPick(o.id);
                    onClose();
                  }}
                  className={cn("flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm", cursor === idx ? "bg-bg" : "")}
                >
                  <TypeIcon type={o.type} />
                  <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  <span className="shrink-0 text-[11px] text-muted">{typeLabel(o.type)}</span>
                </button>
              </li>
            );
          })}
          {debounced.length > 1 && objects.length === 0 && !isFetching ? (
            <li className="px-3 py-3 text-xs text-muted">No object matches “{debounced}”.</li>
          ) : null}
          {debounced.length <= 1 ? (
            <li className="px-3 py-3 text-xs text-muted">Type at least two characters to search the registry.</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}
