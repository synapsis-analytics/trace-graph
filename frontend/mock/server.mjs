/**
 * Mock TRACE API — implements the PLAN.md §4 contract over the fixture graph so the SPA
 * is fully demoable before the real FastAPI backend exists.
 *   node mock/server.mjs           # :8432
 *   PORT=8433 node mock/server.mjs
 * It is a dev aid only: no persistence, no auth beyond a token string comparison.
 */
import express from "express";
import { buildFixture, LENSES } from "./fixture.mjs";

const PORT = Number(process.env.PORT || 8432);
const ACCESS_KEY = process.env.TRACE_ACCESS_KEY || "demo-key";
const ASK_ENABLED = process.env.MOCK_ASK === "1";

const { objects, links, claims } = buildFixture();
const objectList = [...objects.values()];

const outIndex = new Map();
const inIndex = new Map();
for (const l of links) {
  if (!outIndex.has(l.subject)) outIndex.set(l.subject, []);
  outIndex.get(l.subject).push(l);
  if (!inIndex.has(l.object)) inIndex.set(l.object, []);
  inIndex.get(l.object).push(l);
}

const toNode = (o) => ({
  id: o.id,
  type: o.type,
  label: o.label,
  size: nodeSize(o),
  band: o.qa?.band ?? "high",
  attrs: o.attrs ?? {},
});
const toEdge = (l) => ({
  id: l.id,
  source: l.subject,
  target: l.object,
  predicate: l.predicate,
  attrs: { ...(l.attrs ?? {}), band: l.qa?.band, claim_id: l.claim_id },
});

function nodeSize(o) {
  const deg = (outIndex.get(o.id)?.length ?? 0) + (inIndex.get(o.id)?.length ?? 0);
  const base = { program: 8, aow: 7, hlo: 6, outcome: 5, indicator: 4, result: 4, kp: 4 }[o.type] ?? 3;
  return Math.min(18, base + Math.sqrt(deg));
}

const lensByName = new Map(LENSES.map((l) => [l.name, l]));

function lensRules(name) {
  const lens = lensByName.get(name);
  if (!lens) return null;
  const types = new Set();
  const predicates = new Set();
  const triples = new Set();
  for (const path of lens.paths ?? []) {
    for (let i = 0; i < path.length; i += 2) {
      types.add(path[i]);
      if (path[i + 1] && path[i + 2]) {
        predicates.add(path[i + 1]);
        triples.add(`${path[i]}|${path[i + 1]}|${path[i + 2]}`);
        triples.add(`${path[i + 2]}|${path[i + 1]}|${path[i]}`);
      }
    }
  }
  return { types, predicates, triples };
}

function linkAllowed(l, rules) {
  if (!rules) return true;
  const s = objects.get(l.subject);
  const t = objects.get(l.object);
  if (!s || !t) return false;
  if (!rules.predicates.has(l.predicate)) return false;
  return rules.triples.has(`${s.type}|${l.predicate}|${t.type}`);
}

const app = express();
app.use(express.json({ limit: "2mb" }));
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Access-Key");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  // small artificial latency so loading states are visible while developing
  setTimeout(next, Number(process.env.MOCK_LATENCY_MS || 40));
});

const needKey = (req, res) => {
  if (req.get("X-Access-Key") !== ACCESS_KEY) {
    res.status(401).json({ detail: "Missing or invalid X-Access-Key. Set it from the key dialog in the header (mock key: demo-key)." });
    return true;
  }
  return false;
};

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    env: process.env.TRACE_ENV || "mock",
    version: "0.1.0-mock",
    objects: objects.size,
    links: links.length,
    claims: claims.length,
    taxonomy: { url: "http://localhost:8420", reachable: true, version: "v0.2.0" },
  });
});

app.get("/api/stats", (_req, res) => {
  const objects_by_type = {};
  const by_source = {};
  const qa_bands = {};
  for (const o of objectList) {
    objects_by_type[o.type] = (objects_by_type[o.type] ?? 0) + 1;
    const s = o.source?.system ?? "unknown";
    by_source[s] = (by_source[s] ?? 0) + 1;
    const b = o.qa?.band ?? "high";
    qa_bands[b] = (qa_bands[b] ?? 0) + 1;
  }
  const links_by_predicate = {};
  for (const l of links) links_by_predicate[l.predicate] = (links_by_predicate[l.predicate] ?? 0) + 1;
  res.json({
    objects_by_type,
    links_by_predicate,
    qa_bands,
    by_source,
    last_ingest: {
      prms: "2026-09-15T04:12:00Z",
      cgspace: "2026-09-12T02:30:00Z",
      porb: "2026-08-13T10:00:00Z",
      toc: "2026-09-01T09:00:00Z",
      taxonomy: "2026-09-14T22:10:00Z",
    },
    totals: { objects: objects.size, links: links.length, claims: claims.length },
  });
});

app.get("/api/lenses", (_req, res) => res.json({ lenses: LENSES }));

app.get("/api/objects", (req, res) => {
  const { type, q, band, source } = req.query;
  const limit = Math.min(Number(req.query.limit ?? 50), 500);
  const offset = Number(req.query.offset ?? 0);
  const types = type ? String(type).split(",") : null;
  const needle = q ? String(q).toLowerCase() : null;
  let items = objectList.filter((o) => {
    if (types && !types.includes(o.type)) return false;
    if (band && (o.qa?.band ?? "high") !== band) return false;
    if (source && o.source?.system !== source) return false;
    if (needle) {
      const hay = `${o.label} ${o.description ?? ""} ${o.id}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
  if (needle) {
    items = items.sort((a, b) => {
      const ai = a.label.toLowerCase().indexOf(needle);
      const bi = b.label.toLowerCase().indexOf(needle);
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    });
  }
  res.json({ total: items.length, items: items.slice(offset, offset + limit) });
});

app.get("/api/resolve-id", (req, res) => {
  const { scheme, value } = req.query;
  const found = objectList.find((o) => (o.alt_ids ?? []).some((a) => a.scheme === scheme && String(a.value) === String(value)));
  if (!found) return res.status(404).json({ detail: `No object with ${scheme}=${value}` });
  res.json(found);
});

app.get("/api/objects/:id", (req, res) => {
  const o = objects.get(req.params.id);
  if (!o) return res.status(404).json({ detail: `Unknown object ${req.params.id}` });
  const decorate = (l, dir) => ({
    id: l.id,
    predicate: l.predicate,
    subject: l.subject,
    object: l.object,
    attrs: l.attrs,
    qa: l.qa,
    neighbour: (() => {
      const n = objects.get(dir === "out" ? l.object : l.subject);
      return n ? { id: n.id, label: n.label, type: n.type } : undefined;
    })(),
  });
  const links_out = (outIndex.get(o.id) ?? []).map((l) => decorate(l, "out"));
  const links_in = (inIndex.get(o.id) ?? []).map((l) => decorate(l, "in"));
  const tags = (outIndex.get(o.id) ?? [])
    .filter((l) => l.predicate === "TAGGED_WITH")
    .map((l) => {
      const c = objects.get(l.object);
      return { id: l.object, label: c?.label ?? l.object, layer: l.attrs?.layer, via: l.attrs?.via, confidence: l.attrs?.confidence };
    });
  const history = claims
    .filter((c) => c.subject === o.id || c.object === o.id)
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .slice(0, 40)
    .map((c) => ({
      ...c,
      subject_label: c.subject ? objects.get(c.subject)?.label : undefined,
      object_label: c.object ? objects.get(c.object)?.label : undefined,
    }));
  res.json({ ...o, links_out, links_in, tags, claims: history });
});

app.get("/api/objects/:id/neighbourhood", (req, res) => {
  const start = req.params.id;
  if (!objects.has(start)) return res.status(404).json({ detail: `Unknown object ${start}` });
  const depth = Math.min(Math.max(Number(req.query.depth ?? 1), 1), 3);
  const limit = Math.min(Number(req.query.limit ?? 400), 2000);
  const rules = req.query.lens ? lensRules(String(req.query.lens)) : null;
  const preds = req.query.predicates ? new Set(String(req.query.predicates).split(",")) : null;
  const types = req.query.types ? new Set(String(req.query.types).split(",")) : null;

  const seen = new Set([start]);
  const edges = new Map();
  let frontier = [start];
  let truncated = false;
  for (let d = 0; d < depth; d++) {
    const next = [];
    for (const id of frontier) {
      const incident = [...(outIndex.get(id) ?? []), ...(inIndex.get(id) ?? [])];
      for (const l of incident) {
        if (preds && !preds.has(l.predicate)) continue;
        if (!linkAllowed(l, rules)) continue;
        const other = l.subject === id ? l.object : l.subject;
        const otherObj = objects.get(other);
        if (!otherObj) continue;
        if (types && !types.has(otherObj.type)) continue;
        if (seen.size >= limit && !seen.has(other)) { truncated = true; continue; }
        edges.set(l.id, l);
        if (!seen.has(other)) { seen.add(other); next.push(other); }
      }
    }
    frontier = next;
  }
  res.json({
    nodes: [...seen].map((id) => toNode(objects.get(id))),
    edges: [...edges.values()].filter((l) => seen.has(l.subject) && seen.has(l.object)).map(toEdge),
    truncated,
  });
});

app.get("/api/graph", (req, res) => {
  const limit = Math.min(Number(req.query.limit ?? 1500), 5000);
  const rules = req.query.lens ? lensRules(String(req.query.lens)) : null;
  const types = req.query.types ? new Set(String(req.query.types).split(",")) : null;
  const preds = req.query.predicates ? new Set(String(req.query.predicates).split(",")) : null;
  let nodes = objectList.filter((o) => (!types || types.has(o.type)) && (!rules || rules.types.has(o.type)));
  let truncated = false;
  if (nodes.length > limit) { nodes = nodes.slice(0, limit); truncated = true; }
  const ids = new Set(nodes.map((n) => n.id));
  const edges = links.filter(
    (l) => ids.has(l.subject) && ids.has(l.object) && (!preds || preds.has(l.predicate)) && linkAllowed(l, rules),
  );
  res.json({ nodes: nodes.map(toNode), edges: edges.map(toEdge), truncated });
});

app.get("/api/path", (req, res) => {
  const from = String(req.query.from ?? "");
  const to = String(req.query.to ?? "");
  const maxLen = Math.min(Number(req.query.max_len ?? 6), 8);
  const rules = req.query.lens ? lensRules(String(req.query.lens)) : null;
  if (!objects.has(from) || !objects.has(to)) {
    return res.status(404).json({ detail: "Both `from` and `to` must be known TRACE ids." });
  }
  // BFS over links admitted by the lens
  const prev = new Map([[from, null]]);
  const queue = [[from, 0]];
  let found = false;
  while (queue.length) {
    const [id, d] = queue.shift();
    if (id === to) { found = true; break; }
    if (d >= maxLen) continue;
    for (const l of [...(outIndex.get(id) ?? []), ...(inIndex.get(id) ?? [])]) {
      if (!linkAllowed(l, rules)) continue;
      const other = l.subject === id ? l.object : l.subject;
      if (prev.has(other)) continue;
      prev.set(other, { via: l, from: id });
      queue.push([other, d + 1]);
    }
  }
  if (!found) {
    return res.json({
      lens: req.query.lens ?? null,
      paths: [],
      explanation: rules
        ? `No path of ${maxLen} steps or fewer connects these two objects under the "${req.query.lens}" lens. Try a wider lens — the lens deliberately forbids some hops (for example the money lens never walks result → country).`
        : "No path of that length connects these two objects.",
    });
  }
  const hops = [];
  const nodeIds = [];
  let cur = to;
  while (cur) {
    nodeIds.unshift(cur);
    const step = prev.get(cur);
    if (!step) break;
    hops.unshift({ from: step.from, predicate: step.via.predicate, to: cur });
    cur = step.from;
  }
  const words = hops
    .map((h) => `${objects.get(h.from).label} —${h.predicate.toLowerCase().replace(/_/g, " ")}→ ${objects.get(h.to).label}`)
    .join("; then ");
  res.json({
    lens: req.query.lens ?? null,
    paths: [
      {
        nodes: nodeIds.map((id) => toNode(objects.get(id))),
        edges: hops.map((h, i) => ({ id: `path_${i}`, source: h.from, target: h.to, predicate: h.predicate, attrs: {} })),
        hops,
        length: hops.length,
        explanation: `${words}. Every hop is a link admitted by the ${req.query.lens ? `"${req.query.lens}"` : "unrestricted"} lens, so this chain is a valid reading of the evidence.`,
      },
    ],
    explanation: `Shortest valid chain: ${hops.length} hop${hops.length === 1 ? "" : "s"}.`,
  });
});

app.get("/api/coverage", (req, res) => {
  const layer = req.query.layer ? Number(req.query.layer) : null;
  const perConcept = new Map();
  for (const l of links) {
    if (l.predicate !== "TAGGED_WITH") continue;
    const c = objects.get(l.object);
    const s = objects.get(l.subject);
    if (!c || !s) continue;
    if (layer && Number(c.attrs?.layer) !== layer) continue;
    if (!perConcept.has(c.id)) {
      perConcept.set(c.id, { id: c.id, label: c.label, layer: c.attrs?.layer, uri: (c.alt_ids ?? []).find((a) => a.scheme === "taxonomy_uri")?.value, count: 0, by_type: {} });
    }
    const entry = perConcept.get(c.id);
    entry.count += 1;
    entry.by_type[s.type] = (entry.by_type[s.type] ?? 0) + 1;
  }
  const tagged = new Set(links.filter((l) => l.predicate === "TAGGED_WITH").map((l) => l.subject));
  res.json({
    layer: layer ?? "all",
    concepts: [...perConcept.values()].sort((a, b) => b.count - a.count),
    unmatched_terms: [
      { term: "demand-led breeding", count: 34, example: "trace:result:prms-24013" },
      { term: "product advancement meeting", count: 21, example: "trace:result:prms-24052" },
      { term: "stage-gate review", count: 17, example: "trace:kp:hdl-10568-175007" },
      { term: "trait deployment pipeline", count: 12, example: "trace:result:prms-24091" },
      { term: "last-mile seed delivery", count: 9, example: "trace:result:prms-24130" },
      { term: "quality declared seed", count: 7, example: "trace:result:prms-24169" },
      { term: "crossing block optimisation", count: 5, example: "trace:result:prms-24208" },
      { term: "forward breeding", count: 4, example: "trace:kp:hdl-10568-175056" },
    ],
    totals: { tagged_objects: tagged.size, objects: objects.size },
  });
});

app.get("/api/claims", (req, res) => {
  const { status, band, subject, kind } = req.query;
  const limit = Math.min(Number(req.query.limit ?? 100), 1000);
  const offset = Number(req.query.offset ?? 0);
  const items = claims
    .filter((c) => (!status || c.qa?.status === status) && (!band || c.qa?.band === band) && (!subject || c.subject === subject) && (!kind || c.kind === kind))
    .map((c) => ({ ...c, subject_label: c.subject ? objects.get(c.subject)?.label : undefined, object_label: c.object ? objects.get(c.object)?.label : undefined }));
  res.json({ total: items.length, items: items.slice(offset, offset + limit) });
});

app.get("/api/claims/:id", (req, res) => {
  const c = claims.find((x) => x.id === req.params.id);
  if (!c) return res.status(404).json({ detail: "Unknown claim" });
  res.json(c);
});

function runQa(claim) {
  const checks = [];
  const add = (name, ok, note) => checks.push({ name, ok, note });
  const knownPredicates = new Set(links.map((l) => l.predicate));
  add("well_formed", Boolean(claim.kind), claim.kind ? "kind present" : "kind is required");
  add("id_resolvable", Boolean(claim.subject && objects.has(claim.subject)), claim.subject && objects.has(claim.subject) ? "subject resolves" : "subject does not resolve to a TRACE object");
  if (claim.kind === "assert_link") {
    add("object_resolvable", Boolean(claim.object && objects.has(claim.object)), claim.object && objects.has(claim.object) ? "object resolves" : "object does not resolve");
    add("known_predicate", knownPredicates.has(claim.predicate), knownPredicates.has(claim.predicate) ? "predicate in the contract" : "unknown predicate");
    const dup = links.some((l) => l.subject === claim.subject && l.predicate === claim.predicate && l.object === claim.object);
    add("duplicate", !dup, dup ? "an identical link already exists — consider a SAME_AS or a supersede instead" : "no identical link");
  }
  const hasEvidence = Array.isArray(claim.evidence) && claim.evidence.length > 0;
  add("evidence_present", hasEvidence, hasEvidence ? "evidence attached" : "no URL, handle or DOI attached");
  add("provenance_strength", claim.provenance !== "harvested", `provenance = ${claim.provenance ?? "recorded"}`);
  const score = checks.reduce((acc, c) => acc - (c.ok ? 0 : 0.18), 1);
  const bandName = score >= 0.85 ? "high" : score >= 0.6 ? "medium" : "low";
  return {
    band: bandName,
    score: Math.max(0, Number(score.toFixed(2))),
    checks,
    status: bandName === "high" ? "accepted" : bandName === "medium" ? "review" : "rejected",
    decided_by: null,
    decided_at: null,
  };
}

app.post("/api/claims", (req, res) => {
  const dryRun = req.query.dry_run === "1" || req.query.dry_run === "true";
  if (!dryRun && needKey(req, res)) return;
  const body = req.body ?? {};
  const qa = runQa(body);
  const claim = {
    id: dryRun ? "clm_dryrun" : `clm_01J${String(claims.length + 1).padStart(6, "0")}`,
    kind: body.kind ?? "assert_link",
    subject: body.subject ?? null,
    predicate: body.predicate ?? null,
    object: body.object ?? null,
    payload: body.payload ?? {},
    attested_by: body.attested_by ?? "person:anonymous",
    provenance: body.provenance ?? "recorded",
    signature: null,
    evidence: body.evidence ?? [],
    taxonomy_version: "v0.2.0",
    source: { system: "api", ref: "POST /api/claims" },
    created_at: new Date().toISOString(),
    supersedes: body.supersedes ?? null,
    qa,
  };
  if (!dryRun) {
    claims.push(claim);
    if (qa.status === "accepted" && claim.kind === "assert_link" && objects.has(claim.subject) && objects.has(claim.object)) {
      const link = { id: `lnk_${String(links.length + 1).padStart(6, "0")}`, subject: claim.subject, predicate: claim.predicate, object: claim.object, attrs: claim.payload?.attrs ?? {}, claim_id: claim.id, qa: { band: qa.band } };
      links.push(link);
      if (!outIndex.has(link.subject)) outIndex.set(link.subject, []);
      outIndex.get(link.subject).push(link);
      if (!inIndex.has(link.object)) inIndex.set(link.object, []);
      inIndex.get(link.object).push(link);
    }
  }
  res.status(dryRun ? 200 : 201).json(claim);
});

app.post("/api/claims/:id/decide", (req, res) => {
  if (needKey(req, res)) return;
  const c = claims.find((x) => x.id === req.params.id);
  if (!c) return res.status(404).json({ detail: "Unknown claim" });
  const { decision, by, note } = req.body ?? {};
  if (decision !== "accept" && decision !== "reject") {
    return res.status(422).json({ detail: "decision must be 'accept' or 'reject'" });
  }
  // A decision is itself a claim in the real registry; the mock just stamps the QA block.
  c.qa.status = decision === "accept" ? "accepted" : "rejected";
  c.qa.decided_by = by || "person:anonymous";
  c.qa.decided_at = new Date().toISOString();
  c.qa.decision_note = note ?? "";
  res.json(c);
});

app.post("/api/tag", (req, res) => {
  const text = String(req.body?.text ?? "");
  const matches = [];
  for (const o of objectList) {
    if (o.type !== "concept") continue;
    if (text.toLowerCase().includes(o.label.toLowerCase())) {
      matches.push({ term_id: o.attrs?.term_id, pref_label: o.label, matched_text: o.label, layer: o.attrs?.layer, via: "pref_label", uri: (o.alt_ids ?? []).find((a) => a.scheme === "taxonomy_uri")?.value, status: "published" });
    }
  }
  res.json({ matches, unmatched: [] });
});

app.post("/api/ask", (req, res) => {
  if (!ASK_ENABLED) {
    return res.status(503).json({
      detail: "Ask is disabled: no OPENAI_API_KEY is configured on this environment. Everything else in TRACE works without a model key.",
    });
  }
  const q = String(req.body?.question ?? "");
  const cited = objectList.filter((o) => o.type === "result").slice(0, 4);
  res.json({
    answer: `(mock answer) You asked: "${q}". Under the delivery lens, 50 SP01 results in Reporting 2025 contribute to 8 high-level outputs; 12 of them are knowledge products bridged to CGSpace items through SAME_AS links. Counts are distinct by TRACE id.`,
    tool_calls: [
      { name: "trace_search", args: { query: q, limit: 10 } },
      { name: "trace_neighbourhood", args: { id: cited[0]?.id, depth: 2, lens: "delivery" } },
    ],
    objects_cited: cited.map((o) => ({ id: o.id, label: o.label, type: o.type })),
  });
});

app.get("/api/versions", (_req, res) => {
  res.json({
    versions: [
      { version: "v0.1.0", published_at: "2026-09-15T18:00:00Z", objects: objects.size, links: links.length, notes: "First seed snapshot: SP01 slice." },
    ],
  });
});

app.use("/api", (_req, res) => res.status(404).json({ detail: "Not implemented in the mock API" }));

const server = app.listen(PORT, () => {
  console.log(`[mock] TRACE mock API on http://localhost:${PORT} — ${objects.size} objects, ${links.length} links, ${claims.length} claims`);
  console.log(`[mock] write key: ${ACCESS_KEY}  ·  /api/ask ${ASK_ENABLED ? "enabled" : "returns 503 (set MOCK_ASK=1)"}`);
});
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => server.close(() => process.exit(0)));
