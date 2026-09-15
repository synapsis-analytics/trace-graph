import { describe, expect, it } from "vitest";
import {
  applyCommunities,
  applyTypeColours,
  buildGraph,
  circularLayout,
  graphSummary,
  isValidNode,
  neighbourSet,
  runForceAtlas,
} from "./graphAdapter";
import type { GraphPayload } from "./types";

const payload: GraphPayload = {
  nodes: [
    { id: "trace:program:sp01", type: "program", label: "Breeding for Tomorrow", size: 8, band: "high" },
    { id: "trace:result:prms-1", type: "result", label: "A result", band: "medium" },
    { id: "trace:result:prms-2", type: "result", label: "", band: "low" },
    { id: "trace:institution:clarisa-1", type: "institution", label: "KALRO" },
  ],
  edges: [
    { id: "e1", source: "trace:result:prms-1", target: "trace:program:sp01", predicate: "REPORTED_UNDER" },
    { id: "e2", source: "trace:result:prms-2", target: "trace:program:sp01", predicate: "REPORTED_UNDER" },
    { id: "e3", source: "trace:result:prms-1", target: "trace:institution:clarisa-1", predicate: "WITH_PARTNER" },
  ],
};

describe("buildGraph", () => {
  it("maps every valid node and edge into graphology", () => {
    const g = buildGraph(payload);
    expect(g.order).toBe(4);
    expect(g.size).toBe(3);
    expect(g.getNodeAttribute("trace:program:sp01", "nodeType")).toBe("program");
    expect(g.getNodeAttribute("trace:program:sp01", "label")).toBe("Breeding for Tomorrow");
  });

  it("falls back to the id when the label is missing", () => {
    const g = buildGraph(payload);
    expect(g.getNodeAttribute("trace:result:prms-2", "label")).toBe("trace:result:prms-2");
  });

  it("colours nodes by type and fades low QA bands", () => {
    const g = buildGraph(payload);
    expect(g.getNodeAttribute("trace:result:prms-1", "color")).toBe(g.getNodeAttribute("trace:result:prms-2", "color"));
    expect(g.getNodeAttribute("trace:result:prms-2", "opacity")).toBeLessThan(
      g.getNodeAttribute("trace:program:sp01", "opacity"),
    );
  });

  it("drops edges whose endpoints are unknown instead of inventing nodes", () => {
    const g = buildGraph({
      nodes: payload.nodes,
      edges: [...payload.edges, { id: "bad", source: "trace:result:prms-1", target: "trace:ghost:x", predicate: "SAME_AS" }],
    });
    expect(g.order).toBe(4);
    expect(g.size).toBe(3);
  });

  it("ignores self-loops, duplicate edges and malformed nodes", () => {
    const g = buildGraph({
      nodes: [
        ...payload.nodes,
        { id: "", type: "result", label: "no id" },
        { id: "trace:program:sp01", type: "program", label: "duplicate id" },
      ],
      edges: [
        ...payload.edges,
        { id: "dup", source: "trace:result:prms-1", target: "trace:program:sp01", predicate: "REPORTED_UNDER" },
        { id: "loop", source: "trace:program:sp01", target: "trace:program:sp01", predicate: "PART_OF" },
      ],
    });
    expect(g.order).toBe(4);
    expect(g.size).toBe(3);
    expect(g.getNodeAttribute("trace:program:sp01", "label")).toBe("duplicate id");
  });

  it("returns an empty graph for undefined payloads", () => {
    const g = buildGraph(undefined);
    expect(g.order).toBe(0);
    expect(g.size).toBe(0);
  });

  it("sizes hubs larger than leaves", () => {
    const g = buildGraph(payload);
    expect(g.getNodeAttribute("trace:program:sp01", "size")).toBeGreaterThan(
      g.getNodeAttribute("trace:institution:clarisa-1", "size"),
    );
  });

  it("keeps the raw API node available for the UI", () => {
    const g = buildGraph(payload);
    expect(g.getNodeAttribute("trace:result:prms-1", "raw").id).toBe("trace:result:prms-1");
  });
});

describe("layout and colouring helpers", () => {
  it("assigns finite coordinates with ForceAtlas2", () => {
    const g = buildGraph(payload);
    runForceAtlas(g, 20);
    g.forEachNode((_id, attr) => {
      expect(Number.isFinite(attr.x)).toBe(true);
      expect(Number.isFinite(attr.y)).toBe(true);
    });
  });

  it("places nodes on a circle and restores type colours after community colouring", () => {
    const g = buildGraph(payload);
    circularLayout(g, 10);
    const radius = Math.hypot(g.getNodeAttribute("trace:program:sp01", "x"), g.getNodeAttribute("trace:program:sp01", "y"));
    expect(radius).toBeCloseTo(10, 5);

    const before = g.getNodeAttribute("trace:program:sp01", "color");
    applyCommunities(g);
    applyTypeColours(g);
    expect(g.getNodeAttribute("trace:program:sp01", "color")).toBe(before);
  });

  it("reports neighbours and a summary", () => {
    const g = buildGraph(payload);
    expect([...neighbourSet(g, "trace:result:prms-1")].sort()).toEqual(
      ["trace:institution:clarisa-1", "trace:program:sp01", "trace:result:prms-1"].sort(),
    );
    const summary = graphSummary(g);
    expect(summary.byType.result).toBe(2);
    expect(summary.byPredicate.REPORTED_UNDER).toBe(2);
  });

  it("does not throw on an empty graph", () => {
    const g = buildGraph({ nodes: [], edges: [] });
    expect(applyCommunities(g)).toBe(0);
    expect(() => runForceAtlas(g)).not.toThrow();
  });
});

describe("isValidNode", () => {
  it("requires a non-empty string id", () => {
    expect(isValidNode({ id: "x", type: "result", label: "l" })).toBe(true);
    expect(isValidNode({ type: "result", label: "l" })).toBe(false);
    expect(isValidNode(null)).toBe(false);
  });
});
