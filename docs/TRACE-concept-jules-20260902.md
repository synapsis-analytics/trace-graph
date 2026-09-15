# TRACE

### Taxonomy-Referenced Attestation & Continuous Evidence

*A working name — change freely.*

---

## The core idea, in one paragraph

CGIAR's innovations generate impact largely through what happens to them *after* they leave CGIAR's direct control — through partners, scaling actors, and time. Today, evidence of that impact arrives as disconnected fragments, in whatever form and vocabulary each source happens to use, and much of it never reaches PRMS at all. TRACE is a single architecture that gives every innovation a permanent, resolvable identity; lets any party — external partner, or CGIAR's own staff — attach evidence to it in a controlled, verifiable vocabulary; and applies the same quality screening whether that evidence is arriving today, arrived a decade ago, or was generated inside the organization itself.

**The one sentence version:** one identity, one vocabulary, one quality gate — applied everywhere evidence about an innovation lives, forwards and backwards in time, inside the walls and out.

---

## Why this is one framework, not three

It would be easy to treat "let partners submit evidence," "clean up our old archive," and "improve our own reporting quality" as three separate projects. They aren't. All three are the same operation — *take an unstructured claim about an innovation, resolve it against a controlled taxonomy, check it for quality, attach it to the innovation's permanent record* — applied to three different sources. Building it three times would triple the engineering cost for no real gain. Building it once and pointing three intake channels at it is both cheaper and more powerful, because quality patterns learned from one stream (say, common vagueness in old internal reports) sharpen the QA applied to the others.

---

## The architecture, layer by layer

**1. The anchor — persistent identity per innovation**

Every innovation gets one permanent, resolvable identifier (a RAiD, or equivalent PID), independent of any single reporting system. This is the spine everything else attaches to. Your existing PRMS innovation ID doesn't disappear — it becomes an `alternateIdentifier` inside this record, not a replacement.

**2. The vocabulary — a published, machine-readable taxonomy**

The MELIAF Taxonomy, published as a SKOS vocabulary with permanent URIs for every concept (e.g. ` taxonomy.cgiar.org/concept/adoption.direct-beneficiary` ). Every claim about an innovation references these URIs instead of free text, so "what happened" is expressed in a controlled, resolvable vocabulary rather than whatever words the author happened to reach for.

**3. The identity layer — who is making a claim**

For external, forward-flowing claims: lightweight cryptographic identity (`did:web`) lets a partner sign a claim as unmistakably theirs, without needing an account inside a CGIAR system. For internal and retrospective claims, authorship is recorded from whatever metadata already exists (author, unit, review status) rather than cryptographically signed — a real, honestly-labeled difference in provenance strength.

**4. The claims registry — where evidence actually lives**

An append-only store, one thread per innovation, that every intake channel writes into. Each entry: what is claimed, in taxonomy terms; who claims it; when; with what evidence; at what confidence.

**5. The QA and reconciliation engine — one shared quality gate**

A single service that screens every claim, regardless of source, for the failure modes relevant to that source (see below). Confidence-banded output: high confidence auto-accepted, mid-confidence queued for human review, low confidence explicitly labeled rather than hidden or deleted.

**6. The human review queue — one shared destination**

Flagged claims, taxonomy mismatches, and low-confidence historical records all land in the same review workflow, worked by the same people, so review effort compounds instead of fragmenting across three separate systems.

---

## The three intake modes

### Mode A — Forward: partner-submitted claims

A scaling partner, ministry, or downstream actor signs a structured claim referencing an innovation's identifier and submits it directly — no CGIAR account, no manual relay through PPT staff. QA here screens for: duplication across independent partners reporting the same event, implausible jumps, geography/timeframe mismatches.

### Mode B — Backward: the existing knowledge base

The entire existing archive (CGSpace, PRMS records, technical reports, impact cases) gets run through the same taxonomy-resolution engine retrospectively — embedding-matched against the taxonomy, confidence-scored, tagged or flagged for review. This produces, as a byproduct, a live coverage map: which parts of the taxonomy are richly evidenced, which are thin, and which existing records match nothing at all (a genuine taxonomy-gap signal). QA here screens for: internal duplication (the same result reported in three documents as if new each time), unsubstantiated language with no attached quantity/place/date, and implausible figures relative to a project's known scale.

### Mode C — Internal: CGIAR's own live reporting

Staff-authored reports and results narratives, going forward, get run through the identical pipeline in real time rather than being exempted from it. Same taxonomy resolution, same QA screening logic as Mode B, applied at the point of authorship rather than after the fact — so the organization's own input stream gets progressively cleaner instead of just being graded after it's already stale.

---

## What makes the vocabulary get cleaner over time

Every claim, from any of the three modes, that fails to resolve against an existing taxonomy term is not simply rejected — it's routed to the same review queue as a **candidate concept**, carrying the term used, its frequency, and the contexts it appeared in. Approved candidates are published into the taxonomy with a new URI and immediately become resolvable for all future claims, across all three modes. The taxonomy grows from actual usage pressure across the whole organization and its partners, not from a single committee's initial guess.

---

## What's genuinely new here, and what isn't

**Standing on existing standards (not novel):** the PID layer (RAiD/DOI), the identity layer (W3C DID), the claim format (W3C Verifiable Credentials), the vocabulary format (SKOS). None of this requires inventing new cryptography or new data standards.

**Genuinely new integration work:** wiring these standards together around a single claims registry; the taxonomy-resolution and QA-scoring service; the confidence-banding logic; and treating partner claims, historical archive, and internal reporting as one problem with three intake points instead of three separate problems.

---

## Open questions worth resolving early

- Does CGIAR's existing DataCite relationship (via CIAT, IITA, and others) extend to RAiD, or is that a separate registration — worth a direct question to DataCite/ARDC.

- Whether true federated write access (a partner writing directly, scoped, without relay through CGIAR staff) is actually supported by RAiD's Service Point model, or whether TRACE's claims registry needs to sit as an independent layer regardless.

- Who governs taxonomy approval in practice, and how fast that governance loop can turn around a candidate concept without becoming a bottleneck itself.

- For Mode B and C, since there's often no live author to query, whether "flag and grade" (never silently delete or silently trust) is the right permanent policy or just a starting one.
