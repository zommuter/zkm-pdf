# TODO — zkm-pdf

This is a stub. The broader work ledger is the central zkm `TODO.md` (`~/src/zkm/TODO.md`); executor-facing items for THIS repo live in [ROADMAP.md](ROADMAP.md), which is the single source of truth. <!-- lint-ok: file-purpose preamble -->

- [ ] Relay: id:9475 adopt shared `zkm.pdftext` helper + density pilot. ADOPTION SHIPPED 2026-06-24 (a60c76b, seam id:cd59): convert.py routes via `zkm.pdftext.resolve_threshold` against the shared `pdf_text_threshold` key (`min_text_chars` now a deprecated one-release alias). REMAINING: the density-ratio pilot (seam id:8aa4, `[HARD — meeting]`) is DATA-GATED — no `zkm-pdf-skipped.jsonl` corpus exists yet to calibrate against; coordinated with zkm-scan id:02bd. id:1a30 (eml password-token boundary) closed 2026-06-17. <!-- id:32fe -->
