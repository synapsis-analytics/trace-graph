/**
 * Path finder — "how do these two things connect, and is that connection legitimate?"
 * The lens is the point: the same pair of objects can be connected under `delivery`
 * and unreachable under `money`, because money must not walk result → country.
 */
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Route as RouteIcon } from "lucide-react";
import { ObjectSearch } from "@/components/ObjectSearch";
import { TypeBadge, TypeIcon } from "@/components/TypeBits";
import { Badge, Button, Card, Empty, ErrorState, Loading, Select } from "@/components/ui/primitives";
import { useLenses, usePath } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { TraceObject } from "@/lib/types";
import { predicateLabel } from "@/lib/utils";

export default function PathFinder() {
  const [params] = useSearchParams();
  const [from, setFrom] = useState<TraceObject | null>(null);
  const [to, setTo] = useState<TraceObject | null>(null);
  const [lens, setLens] = useState("delivery");
  const { data: lenses } = useLenses();
  const { data, isFetching, error, refetch } = usePath(from?.id ?? null, to?.id ?? null, lens || undefined);

  // Deep link from the detail drawer / the demo script: /path?from=trace:…&to=trace:…&lens=money
  const fromParam = params.get("from");
  const toParam = params.get("to");
  const lensParam = params.get("lens");
  useEffect(() => {
    let cancelled = false;
    if (fromParam && !from) {
      api
        .object(fromParam)
        .then((o) => {
          if (!cancelled) setFrom(o);
        })
        .catch(() => undefined);
    }
    if (toParam && !to) {
      api
        .object(toParam)
        .then((o) => {
          if (!cancelled) setTo(o);
        })
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
  }, [fromParam, from, toParam, to]);

  useEffect(() => {
    if (lensParam) setLens(lensParam);
  }, [lensParam]);

  const lensDef = (lenses ?? []).find((l) => l.name === lens);
  const paths = data?.paths ?? [];

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-5xl space-y-4">
        <header className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <RouteIcon className="h-5 w-5 text-brand" /> Path finder
          </h1>
          <p className="text-sm text-muted">
            Pick two objects and a lens. TRACE returns the shortest chain of links the lens allows, with a plain-English
            reading of it. If there is no path, that is an answer too.
          </p>
        </header>

        <Card className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr]">
            <div className="space-y-1">
              <span className="label">From</span>
              <ObjectSearch value={from} onChange={setFrom} placeholder="Search the first object…" />
            </div>
            <div className="hidden items-end pb-2 md:flex">
              <ArrowRight className="h-4 w-4 text-muted" />
            </div>
            <div className="space-y-1">
              <span className="label">To</span>
              <ObjectSearch value={to} onChange={setTo} placeholder="Search the second object…" />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-56 space-y-1">
              <span className="label">Lens</span>
              <Select value={lens} onChange={(e) => setLens(e.target.value)} aria-label="Lens">
                <option value="">No lens (any link)</option>
                {(lenses ?? []).map((l) => (
                  <option key={l.name} value={l.name}>
                    {l.name}
                  </option>
                ))}
              </Select>
            </div>
            <p className="flex-1 text-[11px] leading-relaxed text-muted">{lensDef?.description ?? "No lens: every link type is traversable."}</p>
            <Button variant="primary" onClick={() => refetch()} disabled={!from || !to}>
              Find path
            </Button>
          </div>
        </Card>

        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : null}
        {isFetching ? <Loading label="Searching for a valid chain…" /> : null}

        {!from || !to ? (
          <Empty title="Choose two objects" hint="Try a PRMS result and the programme it is reported under, then switch the lens to money to see the path disappear." />
        ) : null}

        {!isFetching && from && to && paths.length === 0 && data ? (
          <Card>
            <p className="text-sm font-medium">No valid path under this lens.</p>
            <p className="mt-1 text-xs text-muted">{data.explanation}</p>
          </Card>
        ) : null}

        {from && to
          ? paths.map((p, i) => (
          <Card key={i} className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-brand/10 text-brand">{p.length ?? p.edges.length} hops</Badge>
              {lens ? <Badge className="bg-bg text-muted">lens: {lens}</Badge> : null}
              <Link className="link ml-auto text-xs" to={`/?focus=${encodeURIComponent(from.id)}&lens=${lens}&depth=2`}>
                open in Explore
              </Link>
            </div>

            <ol className="flex flex-wrap items-stretch gap-2">
              {p.nodes.map((n, idx) => (
                <li key={n.id} className="flex items-center gap-2">
                  <Link
                    to={`/?focus=${encodeURIComponent(n.id)}&lens=${lens}`}
                    className="flex max-w-[16rem] flex-col gap-1 rounded-lg border border-line bg-bg/60 p-2 hover:border-brand"
                  >
                    <TypeBadge type={n.type} />
                    <span className="line-clamp-3 text-xs text-ink">{n.label}</span>
                  </Link>
                  {idx < p.edges.length ? (
                    <span className="flex flex-col items-center text-[10px] text-muted">
                      <ArrowRight className="h-4 w-4" />
                      <span className="whitespace-nowrap">{predicateLabel(p.edges[idx].predicate)}</span>
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>

            {p.explanation ? (
              <p className="rounded-lg border border-line bg-bg/60 p-3 text-xs leading-relaxed text-ink">
                <TypeIcon type="document" className="mr-1 inline" />
                {p.explanation}
              </p>
            ) : null}
          </Card>
          ))
          : null}
      </div>
    </div>
  );
}
