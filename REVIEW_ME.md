# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] Parked orphan refs from dead run relay-20260624-191644-13210 are SAFE to reconcile/drop — their work (id:cd59 zkm.pdftext adoption) already landed in main at a60c76b. `relay/orphan/relay-20260624-191644-13210-execute` (76068ff, session-log only) and `…-review` (91a07bf, empty-diff lint-fix handback) hold nothing not already in main. `/relay reconcile` can clear them.
- [ ] id:8aa4 (density-ratio pilot, `[HARD — meeting]`) is DATA-GATED: it cannot start until real `zkm-pdf-skipped.jsonl` skip entries accumulate from production runs to calibrate against. Not pickable by the pool; re-surface only once the corpus exists. (Lane corrected this review from the non-grammar `[HARD — strong model]` the auto-split emitted.)
