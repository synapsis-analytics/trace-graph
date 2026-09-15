/**
 * Registry / Review — the append-only claims log with its QA verdicts.
 * Nothing here is ever edited: accepting or rejecting stamps a decision, a correction is a
 * new claim that supersedes the old one, and rejected claims stay visible.
 */
import { Fragment, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, ClipboardList, Plus, X } from "lucide-react";
import { ObjectSearch } from "@/components/ObjectSearch";
import { BandBadge, StatusBadge } from "@/components/TypeBits";
import {
  Badge, Button, Card, Empty, ErrorState, Field, Input, Loading, Select, Table, Td, Th, Textarea, Tooltip,
} from "@/components/ui/primitives";
import { useClaims } from "@/hooks/useApi";
import { api, HttpError, type NewClaim } from "@/lib/api";
import { accessKeyStore, attestorStore } from "@/lib/storage";
import { PREDICATES, type Claim, type TraceObject } from "@/lib/types";
import { formatDate, predicateLabel, stringifyAttr } from "@/lib/utils";

const KINDS = ["assert_object", "assert_link", "assert_attr", "retract", "candidate_concept"];

export default function Registry() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "review";
  const band = params.get("band") ?? "";
  const kind = params.get("kind") ?? "";
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading, error, refetch } = useClaims({ status: status || undefined, band: band || undefined, kind: kind || undefined, limit: 200 });

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-6xl space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <h1 className="flex items-center gap-2 text-lg font-semibold">
              <ClipboardList className="h-5 w-5 text-brand" /> Claims registry
            </h1>
            <p className="max-w-3xl text-sm text-muted">
              Every fact in TRACE — including every link — entered here as a claim: what, about which objects, by whom, on
              what evidence, under which QA verdict. Claims are never updated or deleted.
            </p>
          </div>
          <Button variant="primary" onClick={() => setShowForm((v) => !v)}>
            <Plus className="h-4 w-4" /> Append a claim
          </Button>
        </header>

        {showForm ? <AppendClaimForm onDone={() => refetch()} /> : null}

        <div className="flex flex-wrap items-end gap-3">
          <div className="w-40 space-y-1">
            <span className="label">Status</span>
            <Select value={status} onChange={(e) => set("status", e.target.value)} aria-label="Status">
              <option value="">All</option>
              <option value="review">Review queue</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
            </Select>
          </div>
          <div className="w-36 space-y-1">
            <span className="label">Band</span>
            <Select value={band} onChange={(e) => set("band", e.target.value)} aria-label="Band">
              <option value="">All</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
          </div>
          <div className="w-48 space-y-1">
            <span className="label">Kind</span>
            <Select value={kind} onChange={(e) => set("kind", e.target.value)} aria-label="Kind">
              <option value="">All</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </Select>
          </div>
          <span className="pb-2 text-xs text-muted">{data ? `${data.total} claims match` : ""}</span>
        </div>

        {isLoading ? <Loading label="Loading the registry…" /> : null}
        {error ? <ErrorState error={error} onRetry={() => refetch()} /> : null}
        {data && data.items.length === 0 ? <Empty title="Nothing in this queue" hint="Change the filters, or append a claim to see the QA gate at work." /> : null}
        {data && data.items.length > 0 ? <ClaimTable claims={data.items} onDecided={() => refetch()} /> : null}
      </div>
    </div>
  );
}

function ClaimTable({ claims, onDecided }: { claims: Claim[]; onDecided: () => void }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "accept" | "reject" }) =>
      api.decideClaim(id, decision, attestorStore.get()),
    onSuccess: () => {
      setMessage(null);
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      onDecided();
    },
    onError: (e) => setMessage(e instanceof HttpError && e.status === 401 ? "A write key is required — open the key dialog in the header." : String((e as Error).message)),
  });

  return (
    <div className="space-y-2">
      {message ? <p className="rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">{message}</p> : null}
      <Table>
        <thead>
          <tr>
            <Th className="w-8"> </Th>
            <Th>Claim</Th>
            <Th className="hidden md:table-cell">Attested by</Th>
            <Th>QA</Th>
            <Th className="hidden lg:table-cell">Created</Th>
            <Th className="w-28">Decision</Th>
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => {
            const open = expanded === c.id;
            return (
              <Fragment key={c.id}>
                <tr className="align-top">
                  <Td>
                    <button type="button" aria-label={open ? "Collapse QA detail" : "Expand QA detail"} onClick={() => setExpanded(open ? null : c.id)} className="text-muted">
                      {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge className="bg-bg text-muted">{c.kind}</Badge>
                      {c.predicate ? <span className="text-xs font-medium">{predicateLabel(c.predicate)}</span> : null}
                    </div>
                    <p className="mt-0.5 text-xs text-ink">
                      {c.subject ? (
                        <Link className="link" to={`/?focus=${encodeURIComponent(c.subject)}`}>
                          {c.subject_label ?? c.subject}
                        </Link>
                      ) : (
                        "—"
                      )}
                      {c.object ? (
                        <>
                          {" → "}
                          <Link className="link" to={`/?focus=${encodeURIComponent(c.object)}`}>
                            {c.object_label ?? c.object}
                          </Link>
                        </>
                      ) : null}
                    </p>
                    <p className="font-mono text-[10px] text-muted">{c.id}</p>
                  </Td>
                  <Td className="hidden md:table-cell">
                    <p className="text-xs">{c.attested_by ?? "—"}</p>
                    <p className="text-[11px] text-muted">{c.provenance ?? "—"}</p>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      <BandBadge band={c.qa?.band} />
                      <StatusBadge status={c.qa?.status} />
                      {typeof c.qa?.score === "number" ? <Badge className="bg-bg text-muted">{c.qa.score.toFixed(2)}</Badge> : null}
                    </div>
                  </Td>
                  <Td className="hidden lg:table-cell">
                    <span className="text-[11px] text-muted">{formatDate(c.created_at)}</span>
                  </Td>
                  <Td>
                    {c.qa?.status === "review" ? (
                      <div className="flex gap-1">
                        <Tooltip label="Accept — the claim materialises into the graph">
                          <Button size="icon" variant="secondary" aria-label="Accept claim" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, decision: "accept" })}>
                            <Check className="h-4 w-4 text-emerald-600" />
                          </Button>
                        </Tooltip>
                        <Tooltip label="Reject — the claim stays in the log, labelled">
                          <Button size="icon" variant="secondary" aria-label="Reject claim" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, decision: "reject" })}>
                            <X className="h-4 w-4 text-rose-600" />
                          </Button>
                        </Tooltip>
                      </div>
                    ) : (
                      <span className="text-[11px] text-muted">{c.qa?.decided_by ? `by ${c.qa.decided_by}` : "—"}</span>
                    )}
                  </Td>
                </tr>
                {open ? (
                  <tr>
                    <Td colSpan={6} className="bg-bg/60">
                      <QaDetail claim={c} />
                    </Td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </Table>
    </div>
  );
}

export function QaDetail({ claim }: { claim: Claim }) {
  const checks = claim.qa?.checks ?? [];
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <h3 className="label mb-1">QA checks</h3>
        {checks.length === 0 ? (
          <p className="text-xs text-muted">No check detail recorded for this claim.</p>
        ) : (
          <ul className="space-y-1">
            {checks.map((k) => (
              <li key={k.name} className="flex items-start gap-2 text-xs">
                {k.ok ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" /> : <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-600" />}
                <span>
                  <span className="font-medium">{k.name}</span>
                  {k.note ? <span className="text-muted"> — {k.note}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-2">
        <div>
          <h3 className="label mb-1">Payload</h3>
          <pre className="max-h-40 overflow-auto rounded-lg border border-line bg-surface p-2 font-mono text-[11px]">{JSON.stringify(claim.payload ?? {}, null, 2)}</pre>
        </div>
        {claim.evidence && claim.evidence.length > 0 ? (
          <div>
            <h3 className="label mb-1">Evidence</h3>
            <ul className="text-xs">
              {claim.evidence.map((e) => (
                <li key={`${e.kind}-${e.value}`} className="truncate">
                  {e.kind}: {e.value}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {claim.supersedes ? (
          <p className="text-xs text-muted">
            supersedes <span className="font-mono">{claim.supersedes}</span>
          </p>
        ) : null}
      </div>
    </div>
  );
}

function AppendClaimForm({ onDone }: { onDone: () => void }) {
  const [subject, setSubject] = useState<TraceObject | null>(null);
  const [object, setObject] = useState<TraceObject | null>(null);
  const [predicate, setPredicate] = useState<string>("WITH_PARTNER");
  const [attrs, setAttrs] = useState('{"role": "contributing"}');
  const [evidence, setEvidence] = useState("");
  const [attested, setAttested] = useState(attestorStore.get());
  const [provenance, setProvenance] = useState("recorded");
  const [preview, setPreview] = useState<Claim | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<Claim | null>(null);

  const claim: NewClaim | null = useMemo(() => {
    if (!subject) return null;
    let parsed: Record<string, unknown> = {};
    try {
      parsed = attrs.trim() ? (JSON.parse(attrs) as Record<string, unknown>) : {};
    } catch {
      return null;
    }
    return {
      kind: "assert_link",
      subject: subject.id,
      predicate,
      object: object?.id,
      payload: { attrs: parsed },
      attested_by: attested,
      provenance,
      evidence: evidence.trim() ? [{ kind: evidence.startsWith("http") ? "url" : "text", value: evidence.trim() }] : [],
    };
  }, [subject, object, predicate, attrs, attested, provenance, evidence]);

  const dryRun = useMutation({
    mutationFn: () => api.appendClaim(claim as NewClaim, true),
    onSuccess: (c) => {
      setPreview(c);
      setError(null);
    },
    onError: (e) => setError((e as Error).message),
  });

  const submit = useMutation({
    mutationFn: () => api.appendClaim(claim as NewClaim, false),
    onSuccess: (c) => {
      setSubmitted(c);
      setError(null);
      onDone();
    },
    onError: (e) =>
      setError(e instanceof HttpError && e.status === 401 ? "A write key is required — open the key dialog in the header." : (e as Error).message),
  });

  const hasKey = Boolean(accessKeyStore.get());

  return (
    <Card className="space-y-3 border-brand/40">
      <h2 className="text-sm font-semibold">Append a claim</h2>
      <p className="text-xs text-muted">
        Anyone can append — the governance is the gate, not the gatekeeper. Run the QA verdict first (dry run); it tells you
        exactly what the engine will say before anything is written.
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="space-y-1">
          <span className="label">Subject</span>
          <ObjectSearch value={subject} onChange={setSubject} placeholder="Subject object…" />
        </div>
        <Field label="Predicate">
          <Select value={predicate} onChange={(e) => setPredicate(e.target.value)}>
            {PREDICATES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <div className="space-y-1">
          <span className="label">Object</span>
          <ObjectSearch value={object} onChange={setObject} placeholder="Object…" />
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Attributes (JSON)" hint={claim === null && subject ? "Invalid JSON — fix it to enable the QA run." : undefined}>
          <Textarea value={attrs} onChange={(e) => setAttrs(e.target.value)} rows={3} className="font-mono text-xs" />
        </Field>
        <Field label="Evidence URL or note">
          <Input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="https://…" />
        </Field>
        <div className="space-y-3">
          <Field label="Attested by">
            <Input value={attested} onChange={(e) => setAttested(e.target.value)} />
          </Field>
          <Field label="Provenance">
            <Select value={provenance} onChange={(e) => setProvenance(e.target.value)}>
              <option value="recorded">recorded</option>
              <option value="signed">signed</option>
              <option value="harvested">harvested</option>
            </Select>
          </Field>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => dryRun.mutate()} disabled={!claim || dryRun.isPending}>
          Run QA (dry run)
        </Button>
        <Button variant="primary" onClick={() => submit.mutate()} disabled={!claim || submit.isPending || !hasKey}>
          Append for real
        </Button>
        {!hasKey ? <span className="text-[11px] text-muted">Set a write key in the header to submit.</span> : null}
      </div>

      {error ? <p className="rounded-lg border border-rose-300 bg-rose-50 p-2 text-xs text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">{error}</p> : null}

      {preview ? (
        <div className="rounded-lg border border-line bg-bg/60 p-3">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold">QA verdict (not written):</span>
            <BandBadge band={preview.qa?.band} />
            <StatusBadge status={preview.qa?.status} />
            {typeof preview.qa?.score === "number" ? <Badge className="bg-surface text-muted">score {preview.qa.score.toFixed(2)}</Badge> : null}
          </div>
          <QaDetail claim={preview} />
        </div>
      ) : null}

      {submitted ? (
        <p className="rounded-lg border border-emerald-300 bg-emerald-50 p-2 text-xs text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
          Appended as <span className="font-mono">{submitted.id}</span> — status {submitted.qa?.status}. Payload:{" "}
          {stringifyAttr(submitted.payload)}
        </p>
      ) : null}
    </Card>
  );
}
