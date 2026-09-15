/**
 * TRACE Graph end-to-end smoke test (WP-I).
 *
 *   BASE=http://127.0.0.1:8431 node tests/e2e/smoke.mjs [--shots docs/img]
 *
 * Clicks through every page of the SPA against a REAL backend and asserts the things a demo
 * depends on. Playwright is not a dependency of this repo: point PLAYWRIGHT to an existing
 * install (default: the shared one on this Mac) or `npm i -D playwright` in frontend/.
 * Exit code 0 = all checks passed; any failure prints "FAIL <check>" and exits 1.
 */
const BASE = process.env.BASE || "http://127.0.0.1:8431";
const PW = process.env.PLAYWRIGHT || "/Users/smithai/workspace/outputs/node_modules/playwright/index.mjs";
const shotsFlag = process.argv.indexOf("--shots");
const SHOTS = shotsFlag > -1 ? process.argv[shotsFlag + 1] : process.env.SHOT_DIR || "docs/img";
const KEY = process.env.TRACE_ACCESS_KEY || "";

const { chromium } = await import(PW);
const fs = await import("node:fs/promises");
await fs.mkdir(SHOTS, { recursive: true });

const results = [];
const noise = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
};
const api = async (path) => (await fetch(`${BASE}${path}`)).json();

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("console", (m) => {
  if (m.type() === "error") noise.push(`[console] ${m.text()}`);
});
page.on("pageerror", (e) => noise.push(`[pageerror] ${e.message}`));
page.on("requestfailed", (r) => {
  if (!r.url().includes("favicon")) noise.push(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`);
});

const shot = async (name) => {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/${name}.png` });
};
const go = async (path) => {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
};

// ---------------------------------------------------------------- health / data present
const health = await api("/health");
check("health.status=ok", health.status === "ok", `env=${health.env} v${health.version}`);
check("taxonomy service reachable", health.taxonomy?.reachable === true,
  `${health.taxonomy?.url} ${health.taxonomy?.version}`);
check("graph is loaded", health.objects > 500 && health.links > 1000,
  `${health.objects} objects / ${health.links} links / ${health.claims} claims`);

// ---------------------------------------------------------------- 1. Explore
await go("/");
await page.waitForSelector('[data-testid="graph-canvas"] canvas', { timeout: 30000 });
const graph = await api("/api/graph?limit=2000");
check("Explore renders ≥200 nodes", graph.nodes.length >= 200,
  `${graph.nodes.length} nodes / ${graph.edges.length} edges`);
const delivery = await api("/api/graph?limit=2000&lens=delivery");
check("lens switch changes the edge count", delivery.edges.length !== graph.edges.length,
  `all=${graph.edges.length} edges, delivery=${delivery.edges.length} edges`);
await shot("explore");

// search by title -> select -> drawer with claim history
const aResult = (await api("/api/objects?type=result&limit=1")).items[0];
const words = aResult.label.split(/\s+/).slice(0, 4).join(" ");
await page.keyboard.press("Meta+k");
await page.waitForTimeout(400);
await page.keyboard.type(words);
await page.waitForTimeout(1500);
const paletteHit = await page.getByText(aResult.label.slice(0, 40), { exact: false }).count();
check("⌘K search finds a result by title", paletteHit > 0, `"${words}" -> ${paletteHit} hit(s)`);
await page.keyboard.press("ArrowDown");
await page.keyboard.press("Enter");
await page.waitForTimeout(2500);
const drawerText = await page.locator("body").innerText();
check("selecting a node opens the detail drawer", drawerText.includes(aResult.label.slice(0, 30)),
  aResult.id);
const historyTab = page.getByRole("button", { name: /History/i }).first();
if (await historyTab.count()) {
  await historyTab.click();
  await page.waitForTimeout(1200);
}
const detail = await api(`/api/objects/${encodeURIComponent(aResult.id)}`);
const afterHistory = await page.locator("body").innerText();
check("drawer shows the claim history", detail.claims.length > 0 && /harvested|recorded|signed/i.test(afterHistory),
  `${detail.claims.length} claims on ${aResult.id}`);
check("links carry a denormalised neighbour",
  detail.links_out.every((l) => l.neighbour && l.neighbour.id),
  `${detail.links_out.length} out / ${detail.links_in.length} in`);
await shot("explore-focus-drawer");

await page.keyboard.press("Meta+k");
await page.waitForTimeout(400);
await page.keyboard.type("maize");
await page.waitForTimeout(1200);
await shot("command-palette");
await page.keyboard.press("Escape");

// ---------------------------------------------------------------- 2. Path finder
const pathApi = await api(
  `/api/path?from=${encodeURIComponent(aResult.id)}&to=trace:program:sp01&lens=delivery`);
check("path result→program under `delivery`", (pathApi.paths || []).length > 0,
  pathApi.explanation || pathApi.reason);
const blocked = await fetch(
  `${BASE}/api/path?from=${encodeURIComponent(aResult.id)}&to=trace:country:ke&lens=money`);
const blockedBody = await blocked.json();
check("blocked lens answers 200 with an explanation, not 404",
  blocked.status === 200 && blockedBody.paths.length === 0 && !!blockedBody.explanation);
await go(`/path?from=${encodeURIComponent(aResult.id)}&to=trace:program:sp01&lens=delivery`);
const pathText = await page.locator("body").innerText();
check("Path page renders the chain", /reported under|Breeding for Tomorrow/i.test(pathText));
await shot("path");

await go(`/path?from=${encodeURIComponent(aResult.id)}&to=trace:country:ke&lens=money`);
await page.waitForTimeout(1500);
const moneyText = await page.locator("body").innerText();
check("money lens refusal is shown as an answer", /no valid path|does not allow|lens/i.test(moneyText));
await shot("path-money-blocked");

// ---------------------------------------------------------------- 3. Framework tree
await go("/framework");
await page.waitForTimeout(1500);
let frameworkText = await page.locator("body").innerText();
if (!/AOW01|Market Intelligence/i.test(frameworkText)) {
  const expander = page.getByText(/Breeding for Tomorrow/i).first();
  if (await expander.count()) {
    await expander.click();
    await page.waitForTimeout(1200);
    frameworkText = await page.locator("body").innerText();
  }
}
check("Framework shows SP01 → AOW01",
  /Breeding for Tomorrow/i.test(frameworkText) && /AOW01|Market Intelligence/i.test(frameworkText));
await shot("framework");

// ---------------------------------------------------------------- 4. Coverage
await go("/coverage");
const coverage = await api("/api/coverage");
const coverageText = await page.locator("body").innerText();
check("Coverage lists concepts", coverage.concepts.length > 10 &&
  coverageText.includes(coverage.concepts[0].label),
  `${coverage.concepts.length} concepts, ${coverage.unmatched_terms.length} candidate terms`);
await shot("coverage");

// ---------------------------------------------------------------- 5. Registry / review queue
await go("/registry?status=review");
await page.waitForTimeout(1500);
const review = await api("/api/claims?status=review&limit=200");
const registryText = await page.locator("body").innerText();
check("Registry lists review claims", review.total > 0 && /review/i.test(registryText),
  `${review.total} claims in the queue`);
await shot("registry");

// dry-run verdict straight from the API (the UI form posts exactly this)
const anInstitution = (await api("/api/objects?type=institution&limit=1")).items[0];
const dry = await fetch(`${BASE}/api/claims?dry_run=1`, {
  method: "POST",
  headers: { "content-type": "application/json", "X-Access-Key": KEY },
  body: JSON.stringify({
    kind: "assert_link", subject: aResult.id, predicate: "WITH_PARTNER",
    object: anInstitution.id, attested_by: "partner:demo-ngo",
    provenance: "signed", evidence: [{ kind: "url", value: "https://example.org/demo" }],
  }),
});
const dryBody = await dry.json();
check("dry-run returns a QA verdict", dry.status === 200 && dryBody.qa?.band === "high" &&
  dryBody.materialised === false,
  `${aResult.id} WITH_PARTNER ${anInstitution.id} -> band=${dryBody.qa?.band} score=${dryBody.qa?.score}`);
await shot("registry-append-dryrun");

// ---------------------------------------------------------------- 6. Ask
await go("/ask");
await page.waitForTimeout(800);
const askProbe = await fetch(`${BASE}/api/ask`, {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ question: "Which partners appear most often?" }),
});
const askTextarea = page.locator("textarea").first();
if (await askTextarea.count()) {
  await askTextarea.fill("Which partners appear most often in SP01?");
  const askBtn = page.getByRole("button", { name: /^Ask/i }).first();
  if (await askBtn.count()) await askBtn.click();
  await page.waitForTimeout(2500);
}
const askText = await page.locator("body").innerText();
check("Ask shows an answer or the no-key notice",
  askProbe.status === 503 ? /key|unavailable|not configured|without a model/i.test(askText)
                          : askProbe.status === 200,
  `POST /api/ask -> ${askProbe.status}`);
await shot("ask-503");

// ---------------------------------------------------------------- 7. API & MCP guide
await go("/api-guide");
const guideText = await page.locator("body").innerText();
check("API & MCP guide renders", /trace_search|MCP/.test(guideText));
await shot("api-guide");

// dark mode (used by the report)
await go("/");
const darkBtn = page.getByRole("button", { name: /dark mode/i }).first();
if (await darkBtn.count()) {
  await darkBtn.click();
  await page.waitForTimeout(2000);
  await shot("explore-dark");
  await darkBtn.click();
}

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
if (noise.length) {
  console.log(`browser noise (${noise.length}):`);
  noise.slice(0, 20).forEach((n) => console.log("  " + n));
}
process.exit(failed.length ? 1 : 0);
