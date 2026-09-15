/**
 * Coverage — where the taxonomy actually touches the portfolio, and where it does not.
 * Left: concepts ranked by tagged objects, as a proportional bar list split by object type
 * (a treemap of one dimension is just a sorted bar list, and bars are readable at this size).
 * Right: the gap panel — Layer-1 terms the AI saw that have no Layer-2/3 match, i.e. the
 * candidate concepts Jules' reconciliation loop is meant to route to the steering group.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Tags } from "lucide-react";
import { TypeIcon } from "@/components/TypeBits";
import { Badge, Card, Empty, ErrorState, Input, Loading, Select } from "@/components/ui/primitives";
import { useCoverage } from "@/hooks/useApi";
import { typeStyle, typeLabel } from "@/lib/theme";
import { formatNumber } from "@/lib/utils";

export default function Coverage() {
  const [layer, setLayer] = useState<number | "all">(2);
  const [query, setQuery] = useState("");
  const { data, isLoading, error, refetch } = useCoverage(layer);

  const concepts = useMemo(() => {
    const items = data?.concepts ?? [];
    if (!query.trim()) return items;
    const needle = query.toLowerCase();
    return items.filter((c) => c.label.toLowerCase().includes(needle));
  }, [data, query]);

  const max = concepts[0]?.count ?? 1;

  if (isLoading) return <Loading label="Computing taxonomy coverage…" />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-6xl space-y-4">
        <header className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Tags className="h-5 w-5 text-brand" /> Taxonomy coverage
          </h1>
          <p className="text-sm text-muted">
            {formatNumber(data?.totals?.tagged_objects)} of {formatNumber(data?.totals?.objects)} objects carry at least one
            taxonomy tag. A concept with no objects is vocabulary nobody is using; a frequent term with no concept is
            vocabulary the taxonomy is missing.
          </p>
        </header>

        <div className="flex flex-wrap items-end gap-3">
          <div className="w-40 space-y-1">
            <span className="label">Layer</span>
            <Select
              value={String(layer)}
              onChange={(e) => setLayer(e.target.value === "all" ? "all" : Number(e.target.value))}
              aria-label="Taxonomy layer"
            >
              <option value="all">All layers</option>
              <option value="1">Layer 1 — AI graph</option>
              <option value="2">Layer 2 — Lexicon</option>
              <option value="3">Layer 3 — climate adaptation</option>
            </Select>
          </div>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter concepts…" aria-label="Filter concepts" className="max-w-xs" />
        </div>

        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Card>
            <h2 className="mb-2 text-sm font-semibold">Concepts by tagged objects</h2>
            {concepts.length === 0 ? (
              <Empty title="No concepts in this layer" hint="Try another layer, or run the taxonomy intake channel." />
            ) : (
              <ul className="space-y-2">
                {concepts.map((c) => (
                  <li key={c.id}>
                    <div className="flex items-center gap-2 text-xs">
                      <Link to={`/?focus=${encodeURIComponent(c.id)}&lens=evidence&depth=1`} className="min-w-0 flex-1 truncate hover:underline">
                        {c.label}
                      </Link>
                      {c.layer ? <Badge className="bg-bg text-muted">L{c.layer}</Badge> : null}
                      <span className="w-10 text-right font-mono text-muted">{c.count}</span>
                    </div>
                    <div className="mt-1 flex h-2.5 w-full overflow-hidden rounded-full bg-bg" title={describe(c.by_type)}>
                      {Object.entries(c.by_type ?? { unknown: c.count }).map(([t, n]) => (
                        <span
                          key={t}
                          title={`${n} ${typeLabel(t)}`}
                          className="h-2.5"
                          style={{ width: `${(n / max) * 100}%`, backgroundColor: typeStyle(t).color }}
                        />
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="h-4 w-4 text-amber-500" /> Gaps — candidate concepts
            </h2>
            <p className="mb-3 text-[11px] leading-relaxed text-muted">
              Terms the text actually uses that have no Layer-2/3 match. Each one becomes a{" "}
              <code className="font-mono">candidate_concept</code> claim in the registry: reviewed here, then proposed to
              the taxonomy service, then re-tagged in the next version.
            </p>
            {(data?.unmatched_terms ?? []).length === 0 ? (
              <Empty title="No unmatched terms" hint="Either the vocabulary is complete or nothing has been ingested yet." />
            ) : (
              <ul className="space-y-1">
                {(data?.unmatched_terms ?? []).map((u) => (
                  <li key={u.term} className="flex items-center gap-2 rounded-lg border border-line bg-bg/60 px-2 py-1.5 text-xs">
                    <TypeIcon type="concept" />
                    <span className="min-w-0 flex-1 truncate">{u.term}</span>
                    <span className="font-mono text-muted">{u.count}×</span>
                    {u.example ? (
                      <Link className="link" to={`/?focus=${encodeURIComponent(u.example)}`}>
                        example
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <Link className="link mt-3 inline-block text-xs" to="/registry?kind=candidate_concept">
              open the candidate queue in the registry →
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}

function describe(byType: Record<string, number> | undefined): string {
  if (!byType) return "";
  return Object.entries(byType)
    .map(([t, n]) => `${n} ${typeLabel(t)}`)
    .join(" · ");
}
