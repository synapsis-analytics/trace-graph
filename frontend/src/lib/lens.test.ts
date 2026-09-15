import { describe, expect, it } from "vitest";
import { bandAtLeast, countByPredicate, countByType, filterGraph, lensRules, mergePayloads } from "./lens";
import type { GraphPayload, Lens } from "./types";

const delivery: Lens = {
  name: "delivery",
  description: "what was delivered where",
  paths: [
    ["result", "CONTRIBUTES_TO", "hlo", "PART_OF", "aow", "PART_OF", "program"],
    ["result", "LOCATED_IN", "country"],
  ],
};

const money: Lens = {
  name: "money",
  description: "funding only",
  paths: [["project", "FUNDED_BY", "hlo", "PART_OF", "aow"]],
};

const payload: GraphPayload = {
  nodes: [
    { id: "r1", type: "result", label: "Result 1", band: "high" },
    { id: "h1", type: "hlo", label: "HLO 1", band: "high" },
    { id: "a1", type: "aow", label: "AoW 1", band: "high" },
    { id: "p1", type: "program", label: "SP01", band: "high" },
    { id: "c1", type: "country", label: "Kenya", band: "medium" },
    { id: "prj", type: "project", label: "Project", band: "low" },
  ],
  edges: [
    { id: "e1", source: "r1", target: "h1", predicate: "CONTRIBUTES_TO" },
    { id: "e2", source: "h1", target: "a1", predicate: "PART_OF" },
    { id: "e3", source: "a1", target: "p1", predicate: "PART_OF" },
    { id: "e4", source: "r1", target: "c1", predicate: "LOCATED_IN" },
    { id: "e5", source: "prj", target: "h1", predicate: "FUNDED_BY" },
  ],
};

describe("lensRules", () => {
  it("derives types, predicates and typed triples from the path patterns", () => {
    const rules = lensRules(delivery)!;
    expect([...rules.types].sort()).toEqual(["aow", "country", "hlo", "program", "result"]);
    expect(rules.predicates.has("CONTRIBUTES_TO")).toBe(true);
    expect(rules.triples.has("result|CONTRIBUTES_TO|hlo")).toBe(true);
    // paths may be traversed backwards
    expect(rules.triples.has("hlo|CONTRIBUTES_TO|result")).toBe(true);
    expect(rules.triples.has("result|FUNDED_BY|project")).toBe(false);
  });

  it("returns null when there is no lens", () => {
    expect(lensRules(undefined)).toBeNull();
    expect(lensRules({ name: "empty" })).toBeNull();
  });
});

describe("filterGraph", () => {
  it("keeps only what the lens admits", () => {
    const out = filterGraph(payload, { lens: delivery });
    expect(out.nodes.map((n) => n.id).sort()).toEqual(["a1", "c1", "h1", "p1", "r1"]);
    expect(out.edges.map((e) => e.id).sort()).toEqual(["e1", "e2", "e3", "e4"]);
  });

  it("refuses the hops a lens forbids (money never walks result → country)", () => {
    const out = filterGraph(payload, { lens: money });
    expect(out.nodes.map((n) => n.id).sort()).toEqual(["a1", "h1", "prj"]);
    expect(out.edges.map((e) => e.predicate).sort()).toEqual(["FUNDED_BY", "PART_OF"]);
    expect(out.edges.some((e) => e.predicate === "LOCATED_IN")).toBe(false);
  });

  it("applies explicit type and predicate chips", () => {
    const byType = filterGraph(payload, { types: ["result", "hlo"] });
    expect(byType.nodes).toHaveLength(2);
    expect(byType.edges.map((e) => e.id)).toEqual(["e1"]);

    const byPredicate = filterGraph(payload, { predicates: ["PART_OF"] });
    expect(byPredicate.edges.map((e) => e.id).sort()).toEqual(["e2", "e3"]);
    expect(byPredicate.nodes).toHaveLength(6);
  });

  it("can drop isolated nodes and filter by minimum QA band", () => {
    const connected = filterGraph(payload, { predicates: ["PART_OF"], keepIsolated: false });
    expect(connected.nodes.map((n) => n.id).sort()).toEqual(["a1", "h1", "p1"]);

    const highOnly = filterGraph(payload, { minBand: "high" });
    expect(highOnly.nodes.map((n) => n.id).sort()).toEqual(["a1", "h1", "p1", "r1"]);
    expect(highOnly.edges.some((e) => e.id === "e4")).toBe(false);
  });

  it("is a no-op without options", () => {
    const out = filterGraph(payload);
    expect(out.nodes).toHaveLength(6);
    expect(out.edges).toHaveLength(5);
  });
});

describe("mergePayloads and counters", () => {
  it("merges without duplicating and prefers the newer node data", () => {
    const merged = mergePayloads(payload, {
      nodes: [
        { id: "r1", type: "result", label: "Result 1 (updated)", band: "high" },
        { id: "x1", type: "kp", label: "New KP" },
      ],
      edges: [
        { id: "e1", source: "r1", target: "h1", predicate: "CONTRIBUTES_TO" },
        { id: "e6", source: "r1", target: "x1", predicate: "EVIDENCED_BY" },
      ],
      truncated: true,
    });
    expect(merged.nodes).toHaveLength(7);
    expect(merged.edges).toHaveLength(6);
    expect(merged.nodes.find((n) => n.id === "r1")?.label).toBe("Result 1 (updated)");
    expect(merged.truncated).toBe(true);
  });

  it("counts by type and predicate", () => {
    expect(countByType(payload.nodes).result).toBe(1);
    expect(countByPredicate(payload.edges).PART_OF).toBe(2);
  });
});

describe("bandAtLeast", () => {
  it("treats a missing band as high and a missing minimum as no filter", () => {
    expect(bandAtLeast(undefined, "high")).toBe(true);
    expect(bandAtLeast("low", undefined)).toBe(true);
    expect(bandAtLeast("medium", "high")).toBe(false);
    expect(bandAtLeast("medium", "low")).toBe(true);
  });
});
