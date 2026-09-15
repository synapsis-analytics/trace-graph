/**
 * API & MCP — the machine side of TRACE, written for a visitor who arrives without context.
 * Static content on purpose: it must render even when the backend is down.
 */
import { useState } from "react";
import { Braces, Bot, Copy, Check, Link2 } from "lucide-react";
import { Badge, Button, Card, Table, Td, Th } from "@/components/ui/primitives";
import { copyToClipboard } from "@/lib/utils";

const ENDPOINTS: [string, string, string][] = [
  ["GET", "/health", "status, environment, version and object/link/claim counts"],
  ["GET", "/api/stats", "counts by type, predicate, QA band and source system; last ingest per channel"],
  ["GET", "/api/objects?type=&q=&limit=&offset=&band=&source=", "list or search objects (full-text on label and description)"],
  ["GET", "/api/objects/{id}", "one object with links in/out, claim history and taxonomy tags"],
  ["GET", "/api/objects/{id}/neighbourhood?depth=1..3&lens=", "the sub-graph around an object"],
  ["GET", "/api/path?from=&to=&lens=&max_len=6", "shortest valid path under a lens, with a plain-English explanation"],
  ["GET", "/api/graph?lens=&types=&limit=", "the whole filtered graph, as {nodes, edges}"],
  ["GET", "/api/lenses", "the named path rules and what each one means"],
  ["GET", "/api/resolve-id?scheme=&value=", "alternate identifier (handle, DOI, PRMS id, ISO2…) to TRACE object"],
  ["GET", "/api/coverage?layer=2", "taxonomy coverage map plus unmatched candidate terms"],
  ["GET", "/api/claims?status=review", "the registry, including the review queue"],
  ["POST", "/api/claims", "append a claim (add ?dry_run=1 for the QA verdict only) — needs X-Access-Key"],
  ["POST", "/api/claims/{id}/decide", "accept or reject a claim under review — needs X-Access-Key"],
  ["POST", "/api/tag", "resolve free text against the taxonomy service"],
  ["POST", "/api/ask", "question the graph in natural language (optional; 503 without a model key)"],
  ["GET", "/api/versions", "published snapshots; GET /api/export/{v}.json|csv|graphml to download one"],
];

const MCP_TOOLS: [string, string][] = [
  ["trace_search(query, type?, limit?)", "find objects by text"],
  ["trace_get(id)", "one object with its links, claims and tags"],
  ["trace_neighbourhood(id, depth?, lens?)", "the sub-graph around an object"],
  ["trace_path(from_id, to_id, lens?)", "how two objects connect under a lens"],
  ["trace_resolve_id(scheme, value)", "handle / DOI / PRMS id → TRACE object"],
  ["trace_coverage(layer?)", "taxonomy coverage and gaps"],
  ["trace_lenses()", "the named path rules"],
  ["trace_claims(status?, subject?)", "registry listing, including the review queue"],
  ["trace_append_claim(claim_json)", "append a claim (needs the access key)"],
  ["trace_tag_text(text)", "taxonomy matches for a piece of text"],
  ["trace_stats()", "portfolio counts"],
];

const CURL = `# everything readable is public — no key needed
curl -s https://p8415.synaptic.synapsis-analytics.com/api/stats | jq

# find an object, then walk its neighbourhood under a lens
curl -s '.../api/objects?q=market%20intelligence&limit=5' | jq '.items[] | {id, type, label}'
curl -s '.../api/objects/trace:hlo:sp01-hlo2-aow1-io1/neighbourhood?depth=2&lens=delivery' | jq '.nodes | length'

# how does this result connect to the programme?
curl -s '.../api/path?from=trace:result:prms-24338&to=trace:program:sp01&lens=delivery' | jq '.paths[0].explanation'

# append a claim — QA verdict first, no write
curl -s -X POST '.../api/claims?dry_run=1' \\
  -H 'Content-Type: application/json' \\
  -d '{"kind":"assert_link","subject":"trace:result:prms-24338","predicate":"WITH_PARTNER",
       "object":"trace:institution:clarisa-2101","attested_by":"partner:demo-ngo","provenance":"signed",
       "evidence":[{"kind":"url","value":"https://example.org/report.pdf"}]}' | jq '.qa'

# for real (write key required)
curl -s -X POST '.../api/claims' -H 'X-Access-Key: $TRACE_ACCESS_KEY' ... `;

const MCP_CONFIG = `{
  "mcpServers": {
    "trace-graph": {
      "type": "http",
      "url": "https://p8415.synaptic.synapsis-analytics.com/mcp",
      "headers": { "X-Access-Key": "\${TRACE_ACCESS_KEY}" }
    }
  }
}`;

export default function ApiGuide() {
  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-4xl space-y-4">
        <header className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Braces className="h-5 w-5 text-brand" /> API &amp; MCP
          </h1>
          <p className="text-sm text-muted">
            The graph you see in the browser is the same graph an agent sees. Reading is open to anyone; writing goes
            through the same QA gate as the ingestion scripts. Interactive OpenAPI lives at{" "}
            <a className="link" href="/docs">
              /docs
            </a>
            .
          </p>
        </header>

        <Card>
          <h2 className="mb-2 text-sm font-semibold">HTTP endpoints</h2>
          <Table>
            <thead>
              <tr>
                <Th className="w-16">Method</Th>
                <Th>Path</Th>
                <Th className="hidden md:table-cell">What you get</Th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map(([m, p, d]) => (
                <tr key={p}>
                  <Td>
                    <Badge className={m === "GET" ? "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300" : "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-300"}>{m}</Badge>
                  </Td>
                  <Td>
                    <code className="font-mono text-xs">{p}</code>
                  </Td>
                  <Td className="hidden md:table-cell text-muted">{d}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <Card>
          <h2 className="mb-2 text-sm font-semibold">Shapes you will get back</h2>
          <p className="mb-2 text-xs text-muted">Graph payloads are deliberately boring — two flat arrays, stable keys.</p>
          <CodeBlock
            code={`node = { id, type, label, size?, band?, attrs: {} }
edge = { id, source, target, predicate, attrs: {} }

object = { id, type, label, description, attrs, alt_ids: [{scheme, value}],
           source: {system, ref, snapshot}, claim_count, qa: {band, score} }

claim  = { id, kind, subject, predicate, object, payload, attested_by,
           provenance: "harvested|recorded|signed", evidence: [{kind, value}],
           supersedes, qa: {band, score, checks: [...], status} }`}
          />
        </Card>

        <Card>
          <h2 className="mb-2 text-sm font-semibold">curl, start to finish</h2>
          <CodeBlock code={CURL} />
        </Card>

        <Card>
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Bot className="h-4 w-4 text-brand" /> MCP server
          </h2>
          <p className="mb-2 text-xs text-muted">
            The same semantics over MCP (streamable HTTP at <code className="font-mono">/mcp</code>, or stdio for local
            use), so an agent can navigate relationships without scraping the UI. Resources:{" "}
            <code className="font-mono">trace://object/&#123;id&#125;</code> and{" "}
            <code className="font-mono">trace://lens/&#123;name&#125;</code>.
          </p>
          <Table className="mb-3">
            <thead>
              <tr>
                <Th>Tool</Th>
                <Th className="hidden md:table-cell">Purpose</Th>
              </tr>
            </thead>
            <tbody>
              {MCP_TOOLS.map(([t, d]) => (
                <tr key={t}>
                  <Td>
                    <code className="font-mono text-xs">{t}</code>
                  </Td>
                  <Td className="hidden md:table-cell text-muted">{d}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <p className="mb-1 text-xs text-muted">Claude / Claude Code configuration:</p>
          <CodeBlock code={MCP_CONFIG} />
        </Card>

        <Card>
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Link2 className="h-4 w-4 text-brand" /> Rules of the game
          </h2>
          <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted">
            <li>Every object has one persistent TRACE id; alternate identifiers resolve to it, titles never do.</li>
            <li>Every fact is a claim: who said it, when, on what evidence, in which vocabulary, with a QA band.</li>
            <li>Nothing is overwritten. A correction is a new claim that supersedes the old one; rejects stay visible.</li>
            <li>Aggregations count distinct by id, and say when an object was reached by more than one path.</li>
            <li>Budgets belong to the object that holds them. They are never prorated across neighbours.</li>
            <li>A lens is the honest answer to “can I walk this path for this question?” — use one.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-lg border border-line bg-bg p-3 font-mono text-[11px] leading-relaxed">{code}</pre>
      <Button
        size="icon"
        variant="ghost"
        aria-label="Copy snippet"
        className="absolute right-1.5 top-1.5"
        onClick={async () => {
          if (await copyToClipboard(code)) {
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }
        }}
      >
        {copied ? <Check className="h-4 w-4 text-brand" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}
