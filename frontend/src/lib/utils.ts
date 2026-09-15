import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number | undefined | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-GB").format(n);
}

export function formatUsd(n: unknown): string {
  const v = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(v)) return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(v);
}

export function formatDate(iso: string | undefined | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleCase(s: string): string {
  return s
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
    .trim();
}

/** Human label for a predicate ("WITH_PARTNER" → "with partner"). */
export function predicateLabel(p: string): string {
  return p.toLowerCase().replace(/_/g, " ");
}

export function truncate(s: string, n = 80): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export function stringifyAttr(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

/** External URL for a known alt-id scheme, when one exists. */
export function altIdUrl(scheme: string, value: string): string | null {
  const s = scheme.toLowerCase();
  if (!value) return null;
  if (s === "cgspace_handle" || s === "handle") {
    return `https://cgspace.cgiar.org/handle/${value.replace(/^https?:\/\/[^/]+\/handle\//, "")}`;
  }
  if (s === "doi") {
    const doi = value.replace(/^https?:\/\/(dx\.)?doi\.org\//, "");
    return `https://doi.org/${doi}`;
  }
  if (s === "taxonomy_uri" || s === "uri" || s === "url") {
    return /^https?:\/\//.test(value) ? value : null;
  }
  return null;
}

export function isUrl(v: unknown): v is string {
  return typeof v === "string" && /^https?:\/\//.test(v);
}

export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number) {
  let t: ReturnType<typeof setTimeout> | undefined;
  return (...args: A) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
