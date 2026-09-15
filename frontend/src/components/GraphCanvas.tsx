/**
 * WebGL graph canvas (sigma.js v3 + graphology).
 * Interactions: hover highlights the neighbourhood and fades the rest · click selects ·
 * double-click asks the parent to expand the node's neighbourhood · edge hover shows the
 * predicate and its attributes · node size comes from `size` (degree-boosted) · QA band
 * drives opacity, low band is drawn faded so weak statements are visible but quiet.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Sigma from "sigma";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import { Camera, Download, LocateFixed, Pause, Play, RotateCcw, CircleDot } from "lucide-react";
import {
  applyCommunities,
  applyTypeColours,
  buildGraph,
  circularLayout,
  forceAtlasSettings,
  neighbourSet,
  runForceAtlas,
  type TraceGraph,
} from "@/lib/graphAdapter";
import type { GraphEdge, GraphNode, GraphPayload } from "@/lib/types";
import { Button, Tooltip } from "./ui/primitives";
import { cn, predicateLabel, stringifyAttr, truncate } from "@/lib/utils";
import { typeLabel } from "@/lib/theme";

export interface GraphCanvasProps {
  payload: GraphPayload;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onExpand?: (id: string) => void;
  community: boolean;
  /** 0.2 … 3 — sigma labelDensity. */
  labelDensity: number;
  className?: string;
}

interface EdgeHover {
  x: number;
  y: number;
  edge: GraphEdge;
  source?: GraphNode;
  target?: GraphNode;
}

export function GraphCanvas({
  payload,
  selectedId,
  onSelect,
  onExpand,
  community,
  labelDensity,
  className,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<TraceGraph | null>(null);
  const layoutRef = useRef<FA2Layout | null>(null);
  const hoveredRef = useRef<string | null>(null);
  const selectedRef = useRef<string | null>(selectedId);
  const [running, setRunning] = useState(false);
  const [edgeHover, setEdgeHover] = useState<EdgeHover | null>(null);

  const graph = useMemo(() => buildGraph(payload), [payload]);
  const nodeById = useMemo(() => new Map(payload.nodes.map((n) => [n.id, n])), [payload.nodes]);

  selectedRef.current = selectedId;

  /* ---- create the renderer once ---- */
  useEffect(() => {
    if (!containerRef.current) return;
    const renderer = new Sigma(graph as never, containerRef.current, {
      renderLabels: true,
      labelDensity,
      labelGridCellSize: 70,
      labelRenderedSizeThreshold: 9,
      defaultEdgeColor: "rgba(100,116,139,0.28)",
      enableEdgeEvents: true,
      zIndex: true,
      minCameraRatio: 0.03,
      maxCameraRatio: 12,
      labelFont: "Inter, ui-sans-serif, system-ui, sans-serif",
      labelSize: 11,
      allowInvalidContainer: true,
    });
    sigmaRef.current = renderer;
    return () => {
      renderer.kill();
      sigmaRef.current = null;
    };
    // the renderer is recreated whenever the graph instance changes (below)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- swap the graph when the payload changes ---- */
  useEffect(() => {
    const renderer = sigmaRef.current;
    if (!renderer) return;
    layoutRef.current?.kill();
    layoutRef.current = null;
    setRunning(false);
    graphRef.current = graph;
    if (graph.order > 0) runForceAtlas(graph, graph.order > 1200 ? 80 : graph.order > 400 ? 200 : 300);
    if (community) applyCommunities(graph);
    renderer.setGraph(graph as never);
    renderer.refresh();
    renderer.getCamera().animatedReset({ duration: 200 });
  }, [graph, community]);

  /* ---- community colouring toggle ---- */
  useEffect(() => {
    const g = graphRef.current;
    if (!g) return;
    if (community) applyCommunities(g);
    else applyTypeColours(g);
    sigmaRef.current?.refresh();
  }, [community]);

  /* ---- label density ---- */
  useEffect(() => {
    sigmaRef.current?.setSetting("labelDensity", labelDensity);
  }, [labelDensity]);

  /* ---- reducers: hover / selection highlighting ---- */
  useEffect(() => {
    const renderer = sigmaRef.current;
    if (!renderer) return;

    renderer.setSetting("nodeReducer", (node, data) => {
      // Always read the graph sigma is currently rendering: the payload can be swapped
      // underneath us (expand, lens change) and a stale closure would throw.
      const current = renderer.getGraph() as TraceGraph;
      const focus = hoveredRef.current ?? selectedRef.current;
      const res: Record<string, unknown> = { ...data };
      if (focus && current.hasNode(focus)) {
        const nbrs = neighbourSet(current, focus);
        if (!nbrs.has(node)) {
          res.color = isDark() ? "rgba(100,116,139,0.30)" : "rgba(148,163,184,0.30)";
          res.label = "";
          res.zIndex = 0;
        } else {
          res.zIndex = 2;
          res.forceLabel = true;
        }
      }
      if (node === selectedRef.current) {
        res.highlighted = true;
        res.size = Math.max(Number(data.size ?? 4) * 1.35, 8);
        res.zIndex = 3;
      }
      if (data.band === "low") res.color = fade(String(res.color ?? data.color), 0.45);
      return res as never;
    });

    renderer.setSetting("edgeReducer", (edge, data) => {
      const current = renderer.getGraph() as TraceGraph;
      const focus = hoveredRef.current ?? selectedRef.current;
      const res: Record<string, unknown> = { ...data };
      if (focus && current.hasEdge(edge) && current.hasNode(focus)) {
        const [s, t] = current.extremities(edge);
        if (s !== focus && t !== focus) {
          res.color = isDark() ? "rgba(100,116,139,0.07)" : "rgba(148,163,184,0.07)";
          res.hidden = false;
        } else {
          res.color = isDark() ? "rgba(45,212,191,0.75)" : "rgba(15,118,110,0.7)";
          res.size = 1.8;
          res.zIndex = 2;
        }
      }
      return res as never;
    });

    const refresh = () => renderer.refresh({ skipIndexation: true });
    const onEnterNode = ({ node }: { node: string }) => {
      hoveredRef.current = node;
      if (containerRef.current) containerRef.current.style.cursor = "pointer";
      refresh();
    };
    const onLeaveNode = () => {
      hoveredRef.current = null;
      if (containerRef.current) containerRef.current.style.cursor = "default";
      refresh();
    };
    const onClickNode = ({ node }: { node: string }) => onSelect(node);
    const onDoubleClickNode = (payloadEvent: { node: string; event: { preventSigmaDefault: () => void } }) => {
      payloadEvent.event.preventSigmaDefault();
      onExpand?.(payloadEvent.node);
    };
    const onClickStage = () => onSelect(null);
    const onEnterEdge = ({ edge, event }: { edge: string; event: { x: number; y: number } }) => {
      const current = renderer.getGraph() as TraceGraph;
      if (!current.hasEdge(edge)) return;
      const attrs = current.getEdgeAttributes(edge);
      const [s, t] = current.extremities(edge);
      setEdgeHover({ x: event.x, y: event.y, edge: attrs.raw, source: nodeById.get(s), target: nodeById.get(t) });
    };
    const onLeaveEdge = () => setEdgeHover(null);

    renderer.on("enterNode", onEnterNode);
    renderer.on("leaveNode", onLeaveNode);
    renderer.on("clickNode", onClickNode);
    renderer.on("doubleClickNode", onDoubleClickNode);
    renderer.on("clickStage", onClickStage);
    renderer.on("enterEdge", onEnterEdge);
    renderer.on("leaveEdge", onLeaveEdge);
    return () => {
      renderer.removeListener("enterNode", onEnterNode);
      renderer.removeListener("leaveNode", onLeaveNode);
      renderer.removeListener("clickNode", onClickNode);
      renderer.removeListener("doubleClickNode", onDoubleClickNode);
      renderer.removeListener("clickStage", onClickStage);
      renderer.removeListener("enterEdge", onEnterEdge);
      renderer.removeListener("leaveEdge", onLeaveEdge);
    };
  }, [graph, nodeById, onExpand, onSelect]);

  /* ---- keep the highlight in sync with external selection ---- */
  useEffect(() => {
    sigmaRef.current?.refresh({ skipIndexation: true });
  }, [selectedId]);

  /* ---- layout controls ---- */
  const toggleLayout = useCallback(() => {
    const g = graphRef.current;
    if (!g || g.order === 0) return;
    if (!layoutRef.current) {
      layoutRef.current = new FA2Layout(g as never, { settings: forceAtlasSettings(g) });
    }
    if (layoutRef.current.isRunning()) {
      layoutRef.current.stop();
      setRunning(false);
    } else {
      layoutRef.current.start();
      setRunning(true);
    }
  }, []);

  const doCircular = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    layoutRef.current?.stop();
    setRunning(false);
    circularLayout(g, 40 + g.order * 0.9);
    sigmaRef.current?.refresh();
    sigmaRef.current?.getCamera().animatedReset({ duration: 200 });
  }, []);

  const doReset = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    layoutRef.current?.stop();
    setRunning(false);
    runForceAtlas(g, 150);
    sigmaRef.current?.refresh();
    sigmaRef.current?.getCamera().animatedReset({ duration: 200 });
  }, []);

  const doCenterSelection = useCallback(() => {
    const renderer = sigmaRef.current;
    const g = graphRef.current;
    if (!renderer || !g || !selectedRef.current || !g.hasNode(selectedRef.current)) return;
    const pos = renderer.getNodeDisplayData(selectedRef.current);
    if (pos) renderer.getCamera().animate({ x: pos.x, y: pos.y, ratio: 0.35 }, { duration: 400 });
  }, []);

  const exportPng = useCallback(() => {
    const renderer = sigmaRef.current;
    if (!renderer) return;
    const canvases = renderer.getCanvases();
    const { width, height } = renderer.getDimensions();
    const out = document.createElement("canvas");
    out.width = width;
    out.height = height;
    const ctx = out.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = getComputedStyle(document.body).backgroundColor || "#ffffff";
    ctx.fillRect(0, 0, width, height);
    for (const layer of Object.keys(canvases)) ctx.drawImage(canvases[layer], 0, 0, width, height);
    const link = document.createElement("a");
    link.download = `trace-graph-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.png`;
    link.href = out.toDataURL("image/png");
    link.click();
  }, []);

  useEffect(() => () => layoutRef.current?.kill(), []);

  return (
    <div className={cn("relative h-full w-full", className)}>
      <div ref={containerRef} className="sigma-container h-full w-full" data-testid="graph-canvas" />

      <div className="absolute left-3 top-3 flex gap-1 rounded-lg border border-line bg-surface/90 p-1 shadow-soft backdrop-blur">
        <Tooltip label={running ? "Stop ForceAtlas2" : "Run ForceAtlas2 layout"}>
          <Button size="icon" variant="ghost" onClick={toggleLayout} aria-label="Toggle force layout">
            {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
        </Tooltip>
        <Tooltip label="Circular layout">
          <Button size="icon" variant="ghost" onClick={doCircular} aria-label="Circular layout">
            <CircleDot className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip label="Reset layout and camera">
          <Button size="icon" variant="ghost" onClick={doReset} aria-label="Reset layout">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip label="Centre on the selected node">
          <Button size="icon" variant="ghost" onClick={doCenterSelection} aria-label="Centre selection">
            <LocateFixed className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Tooltip label="Export the canvas as PNG">
          <Button size="icon" variant="ghost" onClick={exportPng} aria-label="Export PNG">
            <Download className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>

      <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-2 rounded-lg border border-line bg-surface/90 px-2 py-1 text-[11px] text-muted shadow-soft backdrop-blur">
        <Camera className="h-3 w-3" />
        {graph.order.toLocaleString()} nodes · {graph.size.toLocaleString()} links
        {payload.truncated ? <span className="text-amber-600">· truncated by the API</span> : null}
      </div>

      {edgeHover ? (
        <div
          className="pointer-events-none absolute z-20 max-w-xs rounded-lg border border-line bg-surface p-2 text-[11px] shadow-soft"
          style={{ left: Math.min(edgeHover.x + 12, (containerRef.current?.clientWidth ?? 800) - 260), top: edgeHover.y + 12 }}
        >
          <p className="font-semibold text-ink">{predicateLabel(edgeHover.edge.predicate)}</p>
          <p className="text-muted">
            {truncate(edgeHover.source?.label ?? edgeHover.edge.source, 40)}
            <span className="mx-1">→</span>
            {truncate(edgeHover.target?.label ?? edgeHover.edge.target, 40)}
          </p>
          <p className="text-muted">
            {typeLabel(edgeHover.source?.type)} → {typeLabel(edgeHover.target?.type)}
          </p>
          {edgeHover.edge.attrs && Object.keys(edgeHover.edge.attrs).length > 0 ? (
            <ul className="mt-1 space-y-0.5">
              {Object.entries(edgeHover.edge.attrs)
                .slice(0, 5)
                .map(([k, v]) => (
                  <li key={k} className="text-muted">
                    <span className="font-medium text-ink">{k}</span>: {truncate(stringifyAttr(v), 40)}
                  </li>
                ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {graph.order === 0 ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted shadow-soft">
            Nothing to draw with the current filters — widen the lens or clear the type chips.
          </p>
        </div>
      ) : null}
    </div>
  );
}

/** The canvas is WebGL, so it cannot read CSS variables — ask the document instead. */
function isDark(): boolean {
  return typeof document !== "undefined" && document.documentElement.classList.contains("dark");
}

function fade(color: string, alpha: number): string {
  if (color.startsWith("rgba")) return color;
  if (color.startsWith("#") && (color.length === 7 || color.length === 4)) {
    const hex = color.length === 4 ? color.replace(/#(.)(.)(.)/, "#$1$1$2$2$3$3") : color;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return color;
}
