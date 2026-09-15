/**
 * Right-hand detail panel for the selected object: identity, alt-ids (copyable, linked
 * out when the scheme is resolvable), attributes, taxonomy tags, links grouped by
 * predicate (in and out, with counts), and the append-only claim history timeline.
 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Check, Copy, GitBranch, Route, Signature, ShieldCheck, Sprout } from "lucide-react";
import { useObject } from "@/hooks/useApi";
import { BandBadge, StatusBadge, TypeBadge, TypeIcon } from "./TypeBits";
import { Badge, Button, ErrorState, Loading, Tab, TabList, TabPanel, Tabs, Tooltip } from "./ui/primitives";
import { altIdUrl, copyToClipboard, formatDate, formatUsd, isUrl, predicateLabel, stringifyAttr, titleCase } from "@/lib/utils";
import type { Claim, LinkRef } from "@/lib/types";

const MONEY_KEYS = /(budget|amount|usd|cost)/i;

export function NodeDetailDrawer({
  id,
  onSelect,
  onExpand,
}: {
  id: string;
  onSelect: (id: string) => void;
  onExpand?: (id: string) => void;
}) {
  const { data, isLoading, error, refetch } = useObject(id);
  const [tab, setTab] = useState("links");
  const navigate = useNavigate();

  const grouped = useMemo(() => groupLinks(data?.links_out ?? [], data?.links_in ?? []), [data]);

  if (isLoading) return <Loading label="Loading object…" />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <TypeBadge type={data.type} />
          <BandBadge band={data.qa?.band} />
          {typeof data.qa?.score === "number" ? (
            <Badge className="bg-bg text-muted">QA {data.qa.score.toFixed(2)}</Badge>
          ) : null}
          <Badge className="bg-bg text-muted">{data.claim_count ?? 0} claims</Badge>
        </div>
        {data.description ? <p className="text-xs leading-relaxed text-muted">{data.description}</p> : null}
        <CopyRow value={data.id} label="TRACE id" mono />
        {data.source?.system ? (
          <p className="text-[11px] text-muted">
            source: <span className="font-medium text-ink">{data.source.system}</span>
            {data.source.ref ? ` · ${data.source.ref}` : ""}
            {data.source.snapshot ? ` · snapshot ${data.source.snapshot}` : ""}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-1.5 pt-1">
          <Button size="sm" onClick={() => onExpand?.(data.id)} disabled={!onExpand}>
            <GitBranch className="h-3.5 w-3.5" /> Expand neighbourhood
          </Button>
          <Button size="sm" onClick={() => navigate(`/path?from=${encodeURIComponent(data.id)}`)}>
            <Route className="h-3.5 w-3.5" /> Trace path to…
          </Button>
        </div>
      </div>

      <Tabs value={tab} onChange={setTab}>
        <TabList>
          <Tab value="links">Links ({(data.links_out?.length ?? 0) + (data.links_in?.length ?? 0)})</Tab>
          <Tab value="attrs">Attributes</Tab>
          <Tab value="claims">History ({data.claims?.length ?? 0})</Tab>
        </TabList>

        <div className="pt-3">
          <TabPanel value="links">
            {grouped.length === 0 ? (
              <p className="text-xs text-muted">No links recorded for this object yet.</p>
            ) : (
              <div className="space-y-3">
                {grouped.map((group) => (
                  <section key={`${group.predicate}-${group.direction}`}>
                    <h3 className="label mb-1 flex items-center gap-1">
                      {group.direction === "out" ? "→" : "←"} {predicateLabel(group.predicate)}
                      <span className="text-muted/70">({group.links.length})</span>
                    </h3>
                    <ul className="space-y-1">
                      {group.links.map((l) => (
                        <li key={`${l.id}-${group.direction}`}>
                          <button
                            type="button"
                            onClick={() => l.neighbour?.id && onSelect(l.neighbour.id)}
                            className="flex w-full items-start gap-2 rounded-lg border border-line bg-bg/60 px-2 py-1.5 text-left text-xs hover:border-brand"
                          >
                            <TypeIcon type={l.neighbour?.type} className="mt-0.5 shrink-0" />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-ink">{l.neighbour?.label ?? l.neighbour?.id ?? "unknown object"}</span>
                              {l.attrs && Object.keys(l.attrs).length > 0 ? (
                                <span className="block truncate text-[11px] text-muted">
                                  {Object.entries(l.attrs)
                                    .filter(([k]) => k !== "band" && k !== "claim_id")
                                    .slice(0, 3)
                                    .map(([k, v]) => `${k}: ${MONEY_KEYS.test(k) ? formatUsd(v) : stringifyAttr(v)}`)
                                    .join(" · ")}
                                </span>
                              ) : null}
                            </span>
                            {l.qa?.band ? <BandBadge band={l.qa.band} /> : null}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            )}
          </TabPanel>

          <TabPanel value="attrs">
            <div className="space-y-3">
              {data.attrs && Object.keys(data.attrs).length > 0 ? (
                <table className="w-full text-xs">
                  <tbody>
                    {Object.entries(data.attrs).map(([k, v]) => (
                      <tr key={k} className="border-b border-line last:border-0">
                        <td className="py-1.5 pr-2 align-top font-medium text-muted">{titleCase(k)}</td>
                        <td className="py-1.5 align-top text-ink">
                          {isUrl(v) ? (
                            <a className="link inline-flex items-center gap-1" href={v} target="_blank" rel="noreferrer">
                              {stringifyAttr(v)} <ArrowUpRight className="h-3 w-3" />
                            </a>
                          ) : MONEY_KEYS.test(k) ? (
                            <span title="Budgets are attributes of this object and are never prorated across its neighbours.">
                              {formatUsd(v)} <Sprout className="inline h-3 w-3 text-brand" />
                            </span>
                          ) : (
                            stringifyAttr(v)
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-xs text-muted">No attributes recorded.</p>
              )}

              {data.alt_ids && data.alt_ids.length > 0 ? (
                <section>
                  <h3 className="label mb-1">Alternate identifiers</h3>
                  <ul className="space-y-1">
                    {data.alt_ids.map((a) => {
                      const href = altIdUrl(a.scheme, a.value);
                      return (
                        <li key={`${a.scheme}-${a.value}`} className="flex items-center gap-2 text-xs">
                          <span className="chip bg-bg text-muted">{a.scheme}</span>
                          <span className="min-w-0 flex-1 truncate font-mono text-ink">{a.value}</span>
                          {href ? (
                            <a className="link inline-flex items-center gap-0.5" href={href} target="_blank" rel="noreferrer">
                              open <ArrowUpRight className="h-3 w-3" />
                            </a>
                          ) : null}
                          <CopyButton value={a.value} />
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}

              {data.tags && data.tags.length > 0 ? (
                <section>
                  <h3 className="label mb-1">Taxonomy tags</h3>
                  <div className="flex flex-wrap gap-1">
                    {data.tags.map((t) => (
                      <button key={t.id} type="button" onClick={() => onSelect(t.id)} className="chip bg-bg text-ink hover:border-brand">
                        <TypeIcon type="concept" />
                        {t.label}
                        {t.layer ? <span className="text-muted">L{t.layer}</span> : null}
                        {t.via ? <span className="text-muted">{t.via}</span> : null}
                      </button>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          </TabPanel>

          <TabPanel value="claims">
            <ClaimTimeline claims={data.claims ?? []} />
          </TabPanel>
        </div>
      </Tabs>
    </div>
  );
}

interface LinkGroup {
  predicate: string;
  direction: "in" | "out";
  links: LinkRef[];
}

function groupLinks(out: LinkRef[], inn: LinkRef[]): LinkGroup[] {
  const map = new Map<string, LinkGroup>();
  const add = (l: LinkRef, direction: "in" | "out") => {
    const key = `${direction}:${l.predicate}`;
    if (!map.has(key)) map.set(key, { predicate: l.predicate, direction, links: [] });
    map.get(key)!.links.push(l);
  };
  out.forEach((l) => add(l, "out"));
  inn.forEach((l) => add(l, "in"));
  return [...map.values()].sort((a, b) => b.links.length - a.links.length);
}

export function ClaimTimeline({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) return <p className="text-xs text-muted">No claim history for this object.</p>;
  return (
    <ol className="relative space-y-3 border-l border-line pl-4">
      {claims.map((c) => (
        <li key={c.id} className="relative">
          <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-brand" />
          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <span className="font-mono text-muted">{c.id}</span>
            <Badge className="bg-bg text-muted">{predicateLabel(c.kind)}</Badge>
            <StatusBadge status={c.qa?.status} />
            <BandBadge band={c.qa?.band} />
          </div>
          <p className="mt-0.5 text-xs text-ink">
            {c.predicate ? (
              <>
                <span className="font-medium">{predicateLabel(c.predicate)}</span>
                {c.object_label ? <> → {c.object_label}</> : null}
              </>
            ) : (
              stringifyAttr(c.payload)
            )}
          </p>
          <p className="text-[11px] text-muted">
            <Tooltip label={`provenance: ${c.provenance ?? "unknown"}`}>
              <span className="inline-flex items-center gap-1">
                {c.provenance === "signed" ? <Signature className="h-3 w-3" /> : <ShieldCheck className="h-3 w-3" />}
                {c.attested_by ?? "unknown agent"}
              </span>
            </Tooltip>
            {" · "}
            {formatDate(c.created_at)}
            {c.supersedes ? (
              <>
                {" · supersedes "}
                <span className="font-mono">{c.supersedes}</span>
              </>
            ) : null}
          </p>
          {c.evidence && c.evidence.length > 0 ? (
            <ul className="mt-0.5 text-[11px]">
              {c.evidence.map((e) => (
                <li key={`${e.kind}-${e.value}`}>
                  {isUrl(e.value) ? (
                    <a className="link" href={e.value} target="_blank" rel="noreferrer">
                      {e.kind}: {e.value}
                    </a>
                  ) : (
                    <span className="text-muted">
                      {e.kind}: {e.value}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      aria-label="Copy"
      className="text-muted hover:text-ink"
      onClick={async () => {
        if (await copyToClipboard(value)) {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        }
      }}
    >
      {done ? <Check className="h-3.5 w-3.5 text-brand" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

export function CopyRow({ value, label, mono }: { value: string; label: string; mono?: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line bg-bg/60 px-2 py-1">
      <span className="label">{label}</span>
      <span className={`min-w-0 flex-1 truncate text-xs ${mono ? "font-mono" : ""}`}>{value}</span>
      <CopyButton value={value} />
    </div>
  );
}
