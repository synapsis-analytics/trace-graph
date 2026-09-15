import type { ObjectType } from "./types";

/**
 * One palette for the whole app (dataviz rule: colour means type, nothing else).
 * Hues are spread around the wheel but kept at similar lightness/chroma so no type shouts;
 * every colour passes 4.5:1 against white for the text variants used in badges.
 */
export interface TypeStyle {
  /** Graph / swatch colour (WebGL needs a hex string). */
  color: string;
  /** Tailwind classes for the badge (light + dark). */
  badge: string;
  /** Lucide icon name (see components/TypeIcon.tsx). */
  icon: string;
  label: string;
  /** Default node radius weight in the graph. */
  weight: number;
}

export const TYPE_STYLES: Record<string, TypeStyle> = {
  program: { color: "#1d4ed8", badge: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300", icon: "landmark", label: "Program", weight: 6 },
  aow: { color: "#4f46e5", badge: "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-300", icon: "layers", label: "Area of work", weight: 5 },
  hlo: { color: "#7c3aed", badge: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300", icon: "target", label: "High-level output", weight: 4.5 },
  indicator: { color: "#9333ea", badge: "bg-purple-100 text-purple-800 dark:bg-purple-500/15 dark:text-purple-300", icon: "gauge", label: "Indicator / KPI", weight: 3.5 },
  outcome: { color: "#c026d3", badge: "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-500/15 dark:text-fuchsia-300", icon: "flag", label: "Outcome", weight: 4 },
  result: { color: "#0f766e", badge: "bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300", icon: "circle-check", label: "Result", weight: 3 },
  kp: { color: "#0891b2", badge: "bg-cyan-100 text-cyan-800 dark:bg-cyan-500/15 dark:text-cyan-300", icon: "book-open", label: "Knowledge product", weight: 3 },
  innovation: { color: "#ea580c", badge: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300", icon: "lightbulb", label: "Innovation", weight: 3.5 },
  institution: { color: "#b45309", badge: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300", icon: "building-2", label: "Institution", weight: 3.5 },
  country: { color: "#15803d", badge: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300", icon: "map-pin", label: "Country", weight: 3.5 },
  region: { color: "#65a30d", badge: "bg-lime-100 text-lime-900 dark:bg-lime-500/15 dark:text-lime-300", icon: "globe", label: "Region", weight: 3.5 },
  project: { color: "#be123c", badge: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300", icon: "banknote", label: "Project", weight: 3.5 },
  melia_study: { color: "#db2777", badge: "bg-pink-100 text-pink-800 dark:bg-pink-500/15 dark:text-pink-300", icon: "microscope", label: "MELIA study", weight: 3 },
  concept: { color: "#475569", badge: "bg-slate-200 text-slate-800 dark:bg-slate-500/20 dark:text-slate-300", icon: "tag", label: "Concept", weight: 2.5 },
  person: { color: "#0369a1", badge: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300", icon: "user", label: "Person", weight: 2.5 },
  document: { color: "#57534e", badge: "bg-stone-200 text-stone-800 dark:bg-stone-500/20 dark:text-stone-300", icon: "file-text", label: "Document", weight: 3 },
};

export const UNKNOWN_TYPE_STYLE: TypeStyle = {
  color: "#94a3b8",
  badge: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300",
  icon: "circle-help",
  label: "Unknown",
  weight: 2.5,
};

export function typeStyle(type: string | undefined): TypeStyle {
  if (!type) return UNKNOWN_TYPE_STYLE;
  return TYPE_STYLES[type] ?? UNKNOWN_TYPE_STYLE;
}

export function typeLabel(type: string | undefined): string {
  if (!type) return "unknown";
  return TYPE_STYLES[type]?.label ?? type;
}

/** QA band → opacity + ring treatment. Low band = dashed ring, faded. */
export const BAND_STYLES: Record<string, { opacity: number; ring: string; label: string; badge: string }> = {
  high: { opacity: 1, ring: "ring-1 ring-emerald-400", label: "high confidence", badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" },
  medium: { opacity: 0.85, ring: "ring-1 ring-amber-400", label: "medium confidence", badge: "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300" },
  low: { opacity: 0.55, ring: "ring-1 ring-dashed ring-rose-400", label: "low confidence", badge: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300" },
};

export function bandStyle(band: string | undefined) {
  return BAND_STYLES[band ?? ""] ?? { opacity: 0.9, ring: "", label: "unbanded", badge: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300" };
}

/** Qualitative palette used for community colouring (Louvain), max 12 then cycles. */
export const COMMUNITY_PALETTE = [
  "#2563eb", "#0d9488", "#d97706", "#be123c", "#7c3aed", "#65a30d",
  "#0891b2", "#db2777", "#4b5563", "#b45309", "#1d4ed8", "#16a34a",
];

export function communityColor(i: number): string {
  return COMMUNITY_PALETTE[Math.abs(i) % COMMUNITY_PALETTE.length];
}

export const ALL_TYPES: ObjectType[] = [
  "program", "aow", "hlo", "indicator", "outcome", "result", "kp", "innovation",
  "institution", "country", "region", "project", "melia_study", "concept", "person", "document",
];
