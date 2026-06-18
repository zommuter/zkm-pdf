# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-13 — executor (sonnet)

Worked id:2abf/58d7/af0b/1055/03c2 — all five ROUTINE items in a single session.
Introduced _ExtractResult dataclass to carry body, text_chars, encrypted, and error
flags from _extract_text; updated _emit_md and the source_dir loop to branch on
these flags before any store write; _log_skipped now takes a mandatory reason=
kwarg and deduplicates on (sha256, reason, threshold). _get_pdf_meta extended with
subject and keywords extraction; _emit_md maps keywords into tags list. 20/20
tests green including all 7 new roadmap specs and the empty-password pinning guard.
Friction: none — items were cleanly interdependent and fit one session comfortably.

## 2026-06-12 21:47 — reviewer (claude-fable-5)

Handoff: first CLAUDE.md + ARCHITECTURE.md; README de-staled (pre-M2 .env table). Repaired collection-broken test suite (stale pre-SB5 imports, pre-M2 SCREAMING keys) to 14-green baseline. ROADMAP 5 ROUTINE (2abf skip-log dedup, 58d7 encrypted PDFs, af0b corrupt-PDF skip, 1055 threshold counts <!-- page N --> marker bytes — real bug, 03c2 subject/keywords frontmatter) + 1 HARD (9475 calibrate provisional 100-char heuristic). 6 red specs + pinning guard (pypdf transparently decrypts empty-user-password); @manual Gherkin; 4 REVIEW_ME.

## 2026-06-13 10:29 — executor (sonnet, manual relay integration)

feat(convert): encrypted/error skip reasons, keyword→tags, text-char threshold (executor 0954, manual integration)

## 2026-06-13 15:07 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 497e531 audited clean (docs-only, 20 tests green); pruned 3 REVIEW_ME boxes, minted id:1a30 decryption-queue [HARD], refreshed ARCHITECTURE/CLAUDE pointer v1→v2/TODO count

## 2026-06-13 23:49 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 1 commit (daf49df REVIEW_ME triage) audited clean, 20 tests green, roadmap:1055 box confirmed+pruned, no gaming; routine_open=0

## 2026-06-15 18:07 — strong-execute (claude-opus-4-8, fable-standin, relay-loop)

relay(hard) zkm-pdf id:1a30: self-draining encrypted-pending queue + .eml plaintext-password source; 24/24 green

## 2026-06-16 16:27 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

handoff zkm-pdf: C1 docs (relay pointer v2→v4, README de-stale PDF_SOURCE_DIR→source_dir + encrypted-queue), C2 TODO summary fix (1 open HARD id:9475 GATED, 0 ROUTINE), C4 BDD encrypted-PDF scenarios; C3/C5 no-op (no open ROUTINE, sole HARD gated)

## 2026-06-16 19:57 — reviewer (claude-opus-4-8, relay-loop)

review zkm-pdf: 1 commit (88d3c49 relay-human decision on REVIEW_ME id:1a30) audited
clean — doc-only, gaming-scan clean, 24/24 pre-existing tests green. Reverse-handoff
(§5b): the human decision confirmed parts (a) labelled-only bias and (b) EN+DE vocab,
but part (c) token-boundary needs code → qualified as a [ROUTINE] follow-up REUSING
id:1a30 (single-id-two-views): broaden `_scan_passwords` so a labelled password ending
in `.,;:!?` (e.g. `Secret!`) isn't truncated by the trailing rstrip. Wrote red spec
`test_eml_password_with_trailing_punctuation_drains_queue` (`# roadmap:1a30`, RED today,
verified failing against current impl). TODO summary updated 1→2 open ROADMAP items.
REVIEW_ME id:1a30 box stays OPEN (executor follow-up). routine_open=1.

## 2026-06-16 20:57 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 88d3c49 (human decision id:1a30) audited clean, 24/24 green; reverse-handoff qualified id:1a30 token-broadening [ROUTINE] with red spec; routine_open=1

## 2026-06-17 — executor (sonnet)

Worked id:1a30 (trailing-punctuation follow-up) — dropped the `rstrip(".,;:!?")` from `_scan_passwords` in `convert.py` and updated the adjacent comment to reflect the broadened token boundary. The `_PASSWORD_TOKEN_RE` already delimits on whitespace/quotes/brackets, making the trailing strip redundant and harmful. 25/25 tests green. Friction: none — single-line fix, pre-written red spec drove it cleanly.

## 2026-06-17 13:13 — executor (sonnet, relay-loop)

fix(convert): drop trailing rstrip from _scan_passwords so passwords ending in punctuation (e.g. Secret!) are recovered whole and drain the encrypted-pending queue (id:1a30)

## 2026-06-18 10:48 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: window relay-ckpt-20260617-1313..HEAD = 1 commit (7868de1, doc-only —
human ticked the id:1a30 REVIEW_ME box for already-shipped+checkpointed work; the
trailing-rstrip fix e0e96cd/129ebc3 landed at the prior checkpoint). gaming-scan clean;
no src/tests/pyproject changes this window so no resurrection test needed. Full suite
25/25 green; the id:1a30 spec `test_eml_password_with_trailing_punctuation_drains_queue`
confirmed genuinely green via real impl (rstrip removal), not a weakened assertion.
Reverse-handoff (§5b): no new ledger items added this window. Spec-drift clean —
CLAUDE.md pointer v4 == canonical v4, README/ARCHITECTURE already document the
encrypted/eml-password feature. Pruned the resolved id:1a30 REVIEW_ME box (work fully
closed: both ROADMAP entries [x], test green). Only open ROADMAP item is id:9475 [HARD]
— explicitly GATED (real-corpus measurements + cross-repo zkm-scan coordination), not
executor-ready. routine_open=0; verified_green=[1a30].

## 2026-06-18 10:58 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 7868de1 audited clean (doc-only, 25/25 green, id:1a30 verified); pruned resolved REVIEW_ME box; TODO summary 2→1 open; only id:9475 [HARD] GATED remains; routine_open=0
