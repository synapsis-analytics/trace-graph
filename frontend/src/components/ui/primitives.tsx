/**
 * Minimal shadcn/ui-flavoured primitives, hand-rolled so the app has no component
 * framework dependency: button, badge, input, select, textarea, card, tabs, sheet,
 * dialog, tooltip, table, slider, switch, spinner, empty/error states.
 */
import React, { createContext, useContext, useEffect, useId, useRef, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type ButtonSize = "sm" | "md" | "icon";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand/90 border border-transparent",
  secondary: "bg-surface text-ink border border-line hover:bg-bg",
  outline: "bg-transparent text-ink border border-line hover:bg-bg",
  ghost: "bg-transparent text-muted hover:bg-bg hover:text-ink border border-transparent",
  danger: "bg-rose-600 text-white hover:bg-rose-700 border border-transparent",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-7 px-2 text-xs gap-1",
  md: "h-9 px-3 text-sm gap-1.5",
  icon: "h-8 w-8 p-0 justify-center",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({ variant = "secondary", size = "md", className, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      className={cn(
        "inline-flex items-center rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
    />
  );
}

/* ------------------------------------------------------------------- badge */
export function Badge({ className, children, title }: { className?: string; children: React.ReactNode; title?: string }) {
  return (
    <span title={title} className={cn("chip border-transparent", className)}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------- form fields */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return (
      <input
        ref={ref}
        {...rest}
        className={cn(
          "h-9 w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted/70",
          className,
        )}
      />
    );
  },
);

export function Textarea({ className, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={cn(
        "w-full rounded-lg border border-line bg-surface p-3 text-sm text-ink placeholder:text-muted/70",
        className,
      )}
    />
  );
}

export function Select({ className, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      className={cn("h-9 w-full rounded-lg border border-line bg-surface px-2 text-sm text-ink", className)}
    >
      {children}
    </select>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="label block">{label}</span>
      {children}
      {hint ? <span className="block text-[11px] text-muted">{hint}</span> : null}
    </label>
  );
}

export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  className,
  "aria-label": ariaLabel,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <input
      type="range"
      aria-label={ariaLabel}
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onChange(Number(e.target.value))}
      className={cn("h-1.5 w-full cursor-pointer appearance-none rounded-full bg-line accent-brand", className)}
    />
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-brand" : "bg-line",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/* -------------------------------------------------------------------- card */
export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("card p-4", className)}>{children}</div>;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h2 className="text-sm font-semibold text-ink">{children}</h2>
      {right}
    </div>
  );
}

/* -------------------------------------------------------------------- tabs */
interface TabsCtx {
  value: string;
  setValue: (v: string) => void;
  id: string;
}
const TabsContext = createContext<TabsCtx | null>(null);

export function Tabs({ value, onChange, children }: { value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  const id = useId();
  return <TabsContext.Provider value={{ value, setValue: onChange, id }}>{children}</TabsContext.Provider>;
}

export function TabList({ children }: { children: React.ReactNode }) {
  return (
    <div role="tablist" className="flex gap-1 rounded-lg border border-line bg-bg p-1">
      {children}
    </div>
  );
}

export function Tab({ value, children }: { value: string; children: React.ReactNode }) {
  const ctx = useContext(TabsContext);
  if (!ctx) return null;
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => ctx.setValue(value)}
      className={cn(
        "rounded-md px-3 py-1 text-xs font-medium transition-colors",
        active ? "bg-surface text-ink shadow-soft" : "text-muted hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

export function TabPanel({ value, children }: { value: string; children: React.ReactNode }) {
  const ctx = useContext(TabsContext);
  if (!ctx || ctx.value !== value) return null;
  return <div role="tabpanel">{children}</div>;
}

/* ------------------------------------------------------------ sheet/dialog */
export function Sheet({
  open,
  onClose,
  title,
  children,
  width = "w-[28rem]",
}: {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
  width?: string;
}) {
  useEscape(open, onClose);
  if (!open) return null;
  return (
    <aside
      role="dialog"
      aria-label={typeof title === "string" ? title : "Details"}
      className={cn(
        "absolute right-0 top-0 z-30 flex h-full max-w-[92vw] flex-col border-l border-line bg-surface shadow-soft",
        width,
      )}
    >
      <header className="flex items-start justify-between gap-2 border-b border-line p-3">
        <div className="min-w-0">{title}</div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
          <X className="h-4 w-4" />
        </Button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">{children}</div>
    </aside>
  );
}

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  useEscape(open, onClose);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4 pt-24 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-lg rounded-xl border border-line bg-surface shadow-soft"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close dialog">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="p-4">{children}</div>
        {footer ? <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer> : null}
      </div>
    </div>
  );
}

function useEscape(active: boolean, onEscape: () => void) {
  const ref = useRef(onEscape);
  ref.current = onEscape;
  useEffect(() => {
    if (!active) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") ref.current();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [active]);
}

/* ----------------------------------------------------------------- tooltip */
export function Tooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? (
        <span
          role="tooltip"
          className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 w-max max-w-xs -translate-x-1/2 rounded-md border border-line bg-surface px-2 py-1 text-[11px] text-ink shadow-soft"
        >
          {label}
        </span>
      ) : null}
    </span>
  );
}

/* ------------------------------------------------------------------- table */
export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded-lg border border-line", className)}>
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  );
}

export function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn("border-b border-line bg-bg px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted", className)}>{children}</th>;
}

export function Td({ children, className, colSpan }: { children: React.ReactNode; className?: string; colSpan?: number }) {
  return (
    <td colSpan={colSpan} className={cn("table-cell", className)}>
      {children}
    </td>
  );
}

/* --------------------------------------------------------------- feedback */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("inline-block h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand", className)}
    />
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-4 text-sm text-muted">
      <Spinner />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const err = error as { status?: number; message?: string; detail?: string };
  const status = err?.status;
  return (
    <div className="m-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
      <p className="font-semibold">
        {status === 0 ? "The TRACE API is not reachable" : `Request failed${status ? ` (${status})` : ""}`}
      </p>
      <p className="mt-1 opacity-90">{err?.detail || err?.message || "Unknown error"}</p>
      {status === 0 ? (
        <p className="mt-1 text-xs opacity-80">
          In development, start the backend on :8431 or run <code className="font-mono">npm run dev:mock</code>.
        </p>
      ) : null}
      {onRetry ? (
        <Button className="mt-3" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 p-8 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint ? <p className="max-w-md text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
