The six pieces, each answering one small question that falls out of that idea:

Identifier Service — gives each thing (a dataset, an innovation, a Program) a permanent ID that survives edits.
Taxonomy Service — a shared, controlled vocabulary (SKOS) so claims from different people are actually comparable, not just similar-sounding free text.
Identity/Signing Layer — records or verifies who's making a claim.
Claims/Records Registry — where every claim actually lands, append-only; a correction is a new entry that supersedes the old one, never an overwrite.
QA/Reconciliation Engine — scores each incoming claim (duplicate? plausible? well-formed?) and bands it by confidence before it's trusted.
Lineage Graph — once enough of those links accumulate, this is what lets you query the whole chain in one go instead of reconstructing it by hand.
