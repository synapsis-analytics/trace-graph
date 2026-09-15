import {
  Landmark, Layers, Target, Gauge, Flag, CircleCheck, BookOpen, Lightbulb, Building2,
  MapPin, Globe, Banknote, Microscope, Tag, User, FileText, CircleHelp, type LucideIcon,
} from "lucide-react";
import { bandStyle, typeStyle, typeLabel, ALL_TYPES } from "@/lib/theme";
import { Badge, Tooltip } from "./ui/primitives";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  landmark: Landmark, layers: Layers, target: Target, gauge: Gauge, flag: Flag,
  "circle-check": CircleCheck, "book-open": BookOpen, lightbulb: Lightbulb, "building-2": Building2,
  "map-pin": MapPin, globe: Globe, banknote: Banknote, microscope: Microscope, tag: Tag,
  user: User, "file-text": FileText, "circle-help": CircleHelp,
};

export function TypeIcon({ type, className }: { type: string | undefined; className?: string }) {
  const style = typeStyle(type);
  const Icon = ICONS[style.icon] ?? CircleHelp;
  return <Icon className={cn("h-3.5 w-3.5", className)} aria-hidden="true" />;
}

export function TypeBadge({ type, className }: { type: string | undefined; className?: string }) {
  const style = typeStyle(type);
  return (
    <Badge className={cn(style.badge, className)}>
      <TypeIcon type={type} />
      {typeLabel(type)}
    </Badge>
  );
}

export function BandBadge({ band }: { band: string | undefined }) {
  const style = bandStyle(band);
  return (
    <Tooltip label={`QA band: ${style.label}. Low-band statements are kept and shown, never silently deleted.`}>
      <Badge className={style.badge}>{band ?? "unbanded"}</Badge>
    </Tooltip>
  );
}

export function StatusBadge({ status }: { status: string | undefined }) {
  const map: Record<string, string> = {
    accepted: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
    review: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300",
    rejected: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
  };
  return <Badge className={map[status ?? ""] ?? "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300"}>{status ?? "unknown"}</Badge>;
}

/** The single legend used across the app: one colour + icon per object type. */
export function TypeLegend({ counts, active, onToggle }: { counts?: Record<string, number>; active?: string[]; onToggle?: (t: string) => void }) {
  const selected = new Set(active ?? []);
  return (
    <div className="flex flex-wrap gap-1">
      {ALL_TYPES.map((t) => {
        const style = typeStyle(t);
        const count = counts?.[t];
        const isActive = selected.size === 0 || selected.has(t);
        return (
          <button
            key={t}
            type="button"
            disabled={!onToggle}
            onClick={() => onToggle?.(t)}
            title={`${typeLabel(t)}${count !== undefined ? ` — ${count} in view` : ""}`}
            className={cn(
              "chip gap-1.5",
              isActive ? "bg-surface text-ink" : "bg-bg text-muted opacity-50",
              onToggle ? "hover:border-brand" : "cursor-default",
            )}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: style.color }} />
            {typeLabel(t)}
            {count !== undefined ? <span className="text-muted">{count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
