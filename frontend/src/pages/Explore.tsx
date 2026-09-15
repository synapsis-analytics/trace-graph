/**
 * Explore — the network graph.
 * Left rail = lens switcher · type chips with live counts · predicate filter · focus mode
 * (neighbourhood of the selected node at depth 1–3) · community colouring · label density.
 * Canvas = sigma/WebGL. Right = the detail drawer for the selected object.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Crosshair, Eraser, Filter, Palette, Search, Type } from "lucide-react";
import { GraphCanvas } from "@/components/GraphCanvas";
import { NodeDetailDrawer } from "@/components/NodeDetailDrawer";
import { CommandPalette } from "@/components/CommandPalette";
import { TypeBadge, TypeLegend } from "@/components/TypeBits";
import { Badge, Button, ErrorState, Loading, Select, Sheet, Slider, Switch, Tooltip } from "@/components/ui/primitives";
import { useGraph, useLenses, useNeighbourhood, useObject } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { countByPredicate, countByType, filterGraph, mergePayloads } from "@/lib/lens";
import type { GraphPayload } from "@/lib/types";
import { cn, predicateLabel } from "@/lib/utils";

const EMPTY: GraphPayload = { nodes: [], edges: [] };

export default function Explore() {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();

  const focus = params.get("focus");
  const lens = params.get("lens") ?? "";
  const depth = Number(params.get("depth") ?? 2);
  const [selected, setSelected] = useState<string | null>(focus);
  const [typeChips, setTypeChips] = useState<string[]>([]);
  const [predChips, setPredChips] = useState<string[]>([]);
  const [community, setCommunity] = useState(false);
  const [labelDensity, setLabelDensity] = useState(0.6);
  const [expansions, setExpansions] = useState<GraphPayload>(EMPTY);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const { data: lenses } = useLenses();
  const lensDef = useMemo(() => lenses?.find((l) => l.name === lens), [lenses, lens]);

  const whole = useGraph({ lens: lens || undefined, limit: 2000 }, !focus);
  const hood = useNeighbourhood(focus, { depth, lens: lens || undefined, limit: 600 }, Boolean(focus));
  const source = focus ? hood : whole;
  const { data: focusObject } = useObject(focus);

  const base = source.data ?? EMPTY;
  const merged = useMemo(() => mergePayloads(base, expansions), [base, expansions]);
  // With a lens selected we hide objects the lens never connects: a lens answers
  // "which paths are valid for this question", so dangling nodes are noise, not data.
  const filtered = useMemo(
    () => filterGraph(merged, { types: typeChips, predicates: predChips, keepIsolated: !lens || Boolean(focus) }),
    [merged, typeChips, predChips, lens, focus],
  );

  const typeCounts = useMemo(() => countByType(merged.nodes), [merged.nodes]);
  const predCounts = useMemo(() => countByPredicate(merged.edges), [merged.edges]);

  useEffect(() => {
    setExpansions(EMPTY);
  }, [focus, lens, depth]);

  useEffect(() => {
    if (focus) setSelected(focus);
  }, [focus]);

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params);
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const expand = useCallback(
    async (id: string) => {
      const payload = await queryClient.fetchQuery({
        queryKey: ["neighbourhood", id, { depth: 1, lens: lens || undefined, limit: 200 }],
        queryFn: () => api.neighbourhood(id, { depth: 1, lens: lens || undefined, limit: 200 }),
      });
      setExpansions((prev) => mergePayloads(prev, payload));
      setSelected(id);
    },
    [lens, queryClient],
  );

  const togglechip = (list: string[], value: string, setter: (v: string[]) => void) => {
    setter(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  return (
    <div className="flex h-full min-h-0">
      <aside className="rail hidden p-3 lg:block">
        <div className="space-y-4">
          <section>
            <h2 className="label mb-1 flex items-center gap-1">
              <Filter className="h-3 w-3" /> Lens
            </h2>
            <Select value={lens} onChange={(e) => setParam("lens", e.target.value)} aria-label="Lens">
              <option value="">No lens — everything connected to everything</option>
              {(lenses ?? []).map((l) => (
                <option key={l.name} value={l.name}>
                  {l.name}
                </option>
              ))}
            </Select>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              {lensDef?.description ??
                "A lens is a named set of allowed path patterns. Without one you see every link, which is rarely the question you are asking."}
            </p>
          </section>

          <section>
            <h2 className="label mb-1 flex items-center gap-1">
              <Crosshair className="h-3 w-3" /> Focus mode
            </h2>
            {focus ? (
              <div className="space-y-2 rounded-lg border border-line bg-bg/60 p-2">
                <div className="flex items-start gap-2">
                  <TypeBadge type={focusObject?.type} />
                  <span className="min-w-0 flex-1 truncate text-xs">{focusObject?.label ?? focus}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-muted">depth</span>
                  {[1, 2, 3].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setParam("depth", String(d))}
                      className={cn("chip", depth === d ? "bg-brand text-white" : "bg-surface text-muted")}
                    >
                      {d}
                    </button>
                  ))}
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setParam("focus", null)}>
                    <Eraser className="h-3.5 w-3.5" /> clear
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <p className="text-[11px] text-muted">
                  Showing the whole (filtered) graph. Select a node and focus on it to see only its neighbourhood.
                </p>
                <Button size="sm" onClick={() => selected && setParam("focus", selected)} disabled={!selected}>
                  <Crosshair className="h-3.5 w-3.5" /> Focus on selection
                </Button>
              </div>
            )}
          </section>

          <section>
            <h2 className="label mb-1">Object types in view</h2>
            <TypeLegend counts={typeCounts} active={typeChips} onToggle={(t) => togglechip(typeChips, t, setTypeChips)} />
            {typeChips.length > 0 ? (
              <Button size="sm" variant="ghost" className="mt-1" onClick={() => setTypeChips([])}>
                clear type filter
              </Button>
            ) : null}
          </section>

          <section>
            <h2 className="label mb-1">Link predicates</h2>
            <div className="flex flex-wrap gap-1">
              {Object.entries(predCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([p, n]) => {
                  const active = predChips.length === 0 || predChips.includes(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => togglechip(predChips, p, setPredChips)}
                      className={cn("chip", active ? "bg-surface text-ink" : "bg-bg text-muted opacity-50")}
                    >
                      {predicateLabel(p)} <span className="text-muted">{n}</span>
                    </button>
                  );
                })}
            </div>
            {predChips.length > 0 ? (
              <Button size="sm" variant="ghost" className="mt-1" onClick={() => setPredChips([])}>
                clear predicate filter
              </Button>
            ) : null}
          </section>

          <section className="space-y-2">
            <h2 className="label">Display</h2>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1 text-xs text-muted">
                <Palette className="h-3.5 w-3.5" /> community colours
              </span>
              <Switch checked={community} onChange={setCommunity} label="Colour nodes by community" />
            </div>
            <div className="space-y-1">
              <span className="flex items-center gap-1 text-xs text-muted">
                <Type className="h-3.5 w-3.5" /> label density
              </span>
              <Slider value={labelDensity} min={0.2} max={3} step={0.1} onChange={setLabelDensity} aria-label="Label density" />
            </div>
            <Button size="sm" variant="secondary" className="w-full" onClick={() => setPaletteOpen(true)}>
              <Search className="h-3.5 w-3.5" /> Search objects (⌘K)
            </Button>
          </section>

          <section className="text-[11px] leading-relaxed text-muted">
            <p>
              <span className="font-semibold text-ink">Reading the canvas.</span> Colour = object type · size = how connected
              the object is · faded, thin nodes = low QA band (kept, never deleted). Hover to isolate a neighbourhood, click
              to open the detail panel, double-click to pull in one more ring of links.
            </p>
          </section>
        </div>
      </aside>

      <div className="relative min-w-0 flex-1">
        {source.isLoading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg/70">
            <Loading label={focus ? "Loading neighbourhood…" : "Loading graph…"} />
          </div>
        ) : null}
        {source.error ? (
          <ErrorState error={source.error} onRetry={() => source.refetch()} />
        ) : (
          <GraphCanvas
            payload={filtered}
            selectedId={selected}
            onSelect={setSelected}
            onExpand={expand}
            community={community}
            labelDensity={labelDensity}
          />
        )}

        <div className="pointer-events-none absolute right-3 top-3 flex flex-wrap justify-end gap-1">
          {lens ? <Badge className="bg-brand/10 text-brand">lens: {lens}</Badge> : null}
          {focus ? <Badge className="bg-bg text-muted">focus depth {depth}</Badge> : null}
          {filtered.nodes.length !== merged.nodes.length ? (
            <Badge className="bg-bg text-muted">
              {filtered.nodes.length} of {merged.nodes.length} shown
            </Badge>
          ) : null}
        </div>

        <Sheet
          open={Boolean(selected)}
          onClose={() => setSelected(null)}
          width="w-[26rem]"
          title={
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{merged.nodes.find((n) => n.id === selected)?.label ?? selected}</p>
              <Tooltip label="Open this object as the focus of the graph">
                <button type="button" className="text-[11px] text-brand" onClick={() => selected && setParam("focus", selected)}>
                  focus on this object
                </button>
              </Tooltip>
            </div>
          }
        >
          {selected ? <NodeDetailDrawer id={selected} onSelect={setSelected} onExpand={expand} /> : null}
        </Sheet>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onPick={(id) => setParam("focus", id)} />
    </div>
  );
}
