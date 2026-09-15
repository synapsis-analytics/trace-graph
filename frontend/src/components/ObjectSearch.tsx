/** Debounced object search box used by the path finder, the claim form and the palette. */
import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { useDebounced, useObjects } from "@/hooks/useApi";
import { TypeIcon } from "./TypeBits";
import { Input, Spinner } from "./ui/primitives";
import { typeLabel } from "@/lib/theme";
import type { TraceObject } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ObjectSearch({
  value,
  onChange,
  placeholder = "Search objects…",
  type,
  autoFocus,
  className,
}: {
  value: TraceObject | null;
  onChange: (o: TraceObject | null) => void;
  placeholder?: string;
  type?: string;
  autoFocus?: boolean;
  className?: string;
}) {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const debounced = useDebounced(term, 250);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const { data, isFetching } = useObjects({ q: debounced, type, limit: 12 }, open && debounced.length > 1);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  if (value) {
    return (
      <div className={cn("flex items-center gap-2 rounded-lg border border-line bg-surface px-2 py-1.5", className)}>
        <TypeIcon type={value.type} />
        <span className="min-w-0 flex-1 truncate text-sm">{value.label}</span>
        <span className="hidden text-[11px] text-muted sm:inline">{typeLabel(value.type)}</span>
        <button type="button" aria-label="Clear selection" onClick={() => onChange(null)} className="text-muted hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div ref={boxRef} className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
      <Input
        value={term}
        autoFocus={autoFocus}
        onChange={(e) => {
          setTerm(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="pl-8"
        aria-label={placeholder}
      />
      {isFetching ? <Spinner className="absolute right-2.5 top-2.5" /> : null}
      {open && debounced.length > 1 ? (
        <ul className="absolute z-40 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-line bg-surface p-1 shadow-soft">
          {(data?.items ?? []).map((o) => (
            <li key={o.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-bg"
                onClick={() => {
                  onChange(o);
                  setOpen(false);
                  setTerm("");
                }}
              >
                <TypeIcon type={o.type} />
                <span className="min-w-0 flex-1 truncate">{o.label}</span>
                <span className="shrink-0 text-[11px] text-muted">{typeLabel(o.type)}</span>
              </button>
            </li>
          ))}
          {data && data.items.length === 0 ? <li className="px-2 py-2 text-xs text-muted">No object matches “{debounced}”.</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
