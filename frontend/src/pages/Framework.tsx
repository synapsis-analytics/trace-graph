/**
 * Framework — the results-framework hierarchy as a collapsible tree
 * (program → area of work → high-level output → indicator), the shape the PRMS screen shows.
 * Counts are always count-distinct by TRACE id, and each row says how it was reached.
 * Budgets are read from HLO attributes and are never rolled down to neighbours; the
 * programme row sums its HLO budgets, which is the only aggregation the boundary rule allows.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Landmark } from "lucide-react";
import { TypeBadge } from "@/components/TypeBits";
import { Badge, Card, Empty, ErrorState, Input, Loading, Tooltip } from "@/components/ui/primitives";
import { useGraph } from "@/hooks/useApi";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { cn, formatUsd } from "@/lib/utils";

interface TreeNode {
  node: GraphNode;
  children: TreeNode[];
  results: Set<string>;
  partners: Set<string>;
  countries: Set<string>;
  budget: number;
}

const TYPES = ["program", "aow", "hlo", "indicator", "result", "institution", "country"];

export default function Framework() {
  const { data, isLoading, error, refetch } = useGraph({ types: TYPES, limit: 4000 });
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const tree = useMemo(() => (data ? buildTree(data.nodes, data.edges) : []), [data]);

  const filtered = useMemo(() => {
    if (!query.trim()) return tree;
    const needle = query.toLowerCase();
    const match = (t: TreeNode): TreeNode | null => {
      const kids = t.children.map(match).filter(Boolean) as TreeNode[];
      if (t.node.label.toLowerCase().includes(needle) || kids.length > 0) return { ...t, children: kids };
      return null;
    };
    return tree.map(match).filter(Boolean) as TreeNode[];
  }, [tree, query]);

  if (isLoading) return <Loading label="Loading the results framework…" />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-5xl space-y-4">
        <header className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Landmark className="h-5 w-5 text-brand" /> Results framework
          </h1>
          <p className="text-sm text-muted">
            Program → area of work → high-level output → indicator. Numbers on each row are distinct objects reached from
            that node; budgets live on the high-level output and are summed upwards only.
          </p>
        </header>

        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter the framework…"
          aria-label="Filter the framework"
          className="max-w-sm"
        />

        {filtered.length === 0 ? (
          <Empty title="No framework objects" hint="The API returned no program/aow/hlo objects for this environment." />
        ) : (
          <Card className="p-2">
            <ul>
              {filtered.map((t) => (
                <TreeRow key={t.node.id} node={t} depth={0} open={open} setOpen={setOpen} />
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}

function TreeRow({
  node,
  depth,
  open,
  setOpen,
}: {
  node: TreeNode;
  depth: number;
  open: Record<string, boolean>;
  setOpen: (v: Record<string, boolean>) => void;
}) {
  const isOpen = open[node.node.id] ?? depth < 1;
  const hasChildren = node.children.length > 0;
  return (
    <li>
      <div
        className={cn("flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-bg", depth > 0 && "border-l border-line")}
        style={{ marginLeft: depth * 14 }}
      >
        <button
          type="button"
          aria-label={isOpen ? "Collapse" : "Expand"}
          className={cn("mt-0.5 text-muted", !hasChildren && "invisible")}
          onClick={() => setOpen({ ...open, [node.node.id]: !isOpen })}
        >
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <TypeBadge type={node.node.type} />
            <Link to={`/?focus=${encodeURIComponent(node.node.id)}&lens=portfolio&depth=2`} className="min-w-0 text-sm hover:underline">
              {node.node.label}
            </Link>
          </div>
          <div className="mt-0.5 flex flex-wrap gap-1 text-[11px]">
            {node.results.size > 0 ? (
              <Tooltip label="Distinct results that contribute to this node or anything under it (count distinct by TRACE id).">
                <Badge className="bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300">{node.results.size} results</Badge>
              </Tooltip>
            ) : null}
            {node.partners.size > 0 ? (
              <Badge className="bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300">{node.partners.size} partners</Badge>
            ) : null}
            {node.countries.size > 0 ? (
              <Badge className="bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300">{node.countries.size} countries</Badge>
            ) : null}
            {node.budget > 0 ? (
              <Tooltip label="Budget held as an attribute of the high-level output. It is summed upward but never spread sideways to partners, countries or results.">
                <Badge className="bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300">{formatUsd(node.budget)}</Badge>
              </Tooltip>
            ) : null}
          </div>
        </div>
      </div>
      {isOpen && hasChildren ? (
        <ul>
          {node.children.map((c) => (
            <TreeRow key={c.node.id} node={c} depth={depth + 1} open={open} setOpen={setOpen} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** program ← aow ← hlo ← indicator via PART_OF, plus per-node result/partner/country sets. */
export function buildTree(nodes: GraphNode[], edges: GraphEdge[]): TreeNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const make = (n: GraphNode): TreeNode => ({
    node: n,
    children: [],
    results: new Set(),
    partners: new Set(),
    countries: new Set(),
    budget: Number(n.attrs?.budget_usd ?? 0) || 0,
  });
  const tnodes = new Map<string, TreeNode>();
  for (const n of nodes) {
    if (["program", "aow", "hlo", "indicator"].includes(n.type)) tnodes.set(n.id, make(n));
  }

  for (const e of edges) {
    if (e.predicate !== "PART_OF") continue;
    const child = tnodes.get(e.source);
    const parent = tnodes.get(e.target);
    if (child && parent) parent.children.push(child);
  }

  for (const e of edges) {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) continue;
    if (e.predicate === "CONTRIBUTES_TO" && s.type === "result") tnodes.get(t.id)?.results.add(s.id);
    if (e.predicate === "WITH_PARTNER" && t.type === "institution") tnodes.get(s.id)?.partners.add(t.id);
    if (e.predicate === "LOCATED_IN" && t.type === "country") tnodes.get(s.id)?.countries.add(t.id);
  }

  // roll up child sets and budgets into the parents (distinct by id at every level)
  const rollup = (t: TreeNode, seen = new Set<string>()): TreeNode => {
    if (seen.has(t.node.id)) return t;
    seen.add(t.node.id);
    for (const c of t.children) {
      rollup(c, seen);
      c.results.forEach((r) => t.results.add(r));
      c.partners.forEach((p) => t.partners.add(p));
      c.countries.forEach((x) => t.countries.add(x));
      // Money boundary: an HLO's budget is its own PORB attribute (already the sum of its indicator rows),
      // so indicator budgets are never added into it again; only hlo → aow → program sums upward.
      if (t.node.type !== "hlo") t.budget += c.budget;
    }
    t.children.sort((a, b) => a.node.label.localeCompare(b.node.label));
    return t;
  };

  const childIds = new Set<string>();
  for (const t of tnodes.values()) for (const c of t.children) childIds.add(c.node.id);
  const roots = [...tnodes.values()].filter((t) => !childIds.has(t.node.id));
  roots.forEach((r) => rollup(r));
  return roots
    .filter((r) => r.children.length > 0 || r.node.type === "program")
    .sort((a, b) => b.results.size - a.results.size || a.node.label.localeCompare(b.node.label));
}
