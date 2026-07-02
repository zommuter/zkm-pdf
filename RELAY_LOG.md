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

## 2026-06-18 16:16 — reviewer (claude-opus-4-8[1m], fable-standin, relay-loop)

review zkm-pdf: window relay-ckpt-20260618-1058..HEAD = 1 commit (ddcf065, ROADMAP-only —
/meeting --cross gated-HARD triage annotated id:9475 as DECIDED+SUBSUMED into zkm-scan
id:02bd: extract one `zkm.pdftext` core helper + shared `pdf_text_threshold`, pilot
per-page density vs evidence-backed char-count default on the skip-log corpus; don't
recalibrate in isolation = avoids cross-plugin drift). No src/tests/pyproject changes —
gaming-scan clean, no resurrection/fixture checks needed. Reverse-handoff (§5b): no new
open ledger items added this window (the commit only enriches existing id:9475 prose).
Spec-drift clean — CLAUDE.md pointer v4 == canonical v4. Synced the TODO id:32fe tracking
line to mirror the subsumption decision (single-id-two-views consistency). Only open
ROADMAP item is id:9475 [HARD] — GATED under cross-repo id:02bd, not executor-ready.
routine_open=0; verified_green=[]; gaming_flags=[]; reopened=[].

## 2026-06-18 16:53 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: audited ddcf065 (/meeting --cross subsumed id:9475 into zkm-scan id:02bd); gaming-scan clean, no code/test changes; synced TODO id:32fe; only id:9475 [HARD] GATED remains; routine_open=0

## 2026-06-21 21:34 — reconcile (claude-opus-4-8)

reconcile A/B: id:1a30 password-boundary — keep parked fix (strip .,;:? not !), regression test folded; main's e0e96cd missed mid-sentence trailing period; suite 26/26

## 2026-06-22 16:01 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: window relay-ckpt-20260621-2134..HEAD = 2 commits — 141943c (relay(human)
lane-tag migration id:9475 [HARD — strong model] → [HARD — meeting], id:78ff explicit-lane
convention) and d094ed2 (chore: uv.lock zkm 0.14.0 → 0.15.0 sync to parent). No src/tests
changes — gaming-scan clean; no resurrection/fixture/skip checks needed. Test suite 26/26
green (run from main checkout — worktree's `zkm = {path="../.."}` editable dep can't resolve
the relative path; diff has no code/test delta so green state is inherited from prior ckpt).
Reverse-handoff (§5b): no new open ledger items — the only `+ - [ ]` line is the id:9475
lane-tag rewrite of a pre-existing, already-qualified, decision-gated item. Spec-drift clean:
CLAUDE.md contract pointer v4 == canonical v4; no new commands/features so README/ARCHITECTURE
unaffected. Only open ROADMAP item is id:9475 [HARD — meeting] — DECIDED+SUBSUMED under
cross-repo zkm-scan id:02bd, not executor-ready. routine_open=0; verified_green=[];
gaming_flags=[]; reopened=[].

## 2026-06-22 16:13 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf relay-ckpt-20260621-2134..HEAD: 2 trivial commits (lane-tag id:9475, uv.lock sync), CLEAN by vacuity, suite 26/26, routine_open=0

## 2026-06-22 21:26 — maintenance (manual, uv.lock cascade)

uv.lock cascade refresh to zkm 0.16.0 — mechanical version-pin only (id:bae5), audit-exempt class (no code/spec change).
## 2026-06-22 15:36 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: audited 141943c (relay(human) lane-tag migration id:78ff) — doc-only, gaming-scan clean, no code/test changes; 26/26 tests green (main checkout; worktree-relative editable `zkm = ../..` dep can't resolve from the relay worktree path — known limitation, not a defect). Verified id:9475 retag `[HARD — strong model]`→`[HARD — meeting]` correct: item is DECIDED/SUBSUMED into zkm-scan id:02bd, needs a /meeting design decision not hands-on build (matches hard-lane-explicit grammar). Cross-ledger consistent (id:9475 open in both ROADMAP + TODO id:32fe); contract pointer v4 current. No ROADMAP changes; routine_open=0 (only open item is the gated [HARD — meeting] id:9475).

## 2026-06-23 15:38 — reconcile (human)

reconcile integrate: relay(review): audit 141943c lane-tag migration (id:78ff) — clean, doc-only, 26/26 green

## 2026-06-24 17:23 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 130c305 9475 re-scope ([HARD — meeting]→[HARD — pool]) verified legit; reconciled TODO twin id:32fe single-id divergence; suite green (26), no gaming

## 2026-06-24 21:01 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

Review zkm-pdf: id:cd59 (zkm.pdftext adoption) verified genuinely green + closed; id:8aa4 lane fixed to [HARD — meeting]; README drift fixed; 28 tests green

## 2026-06-25 14:35 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: 2 /relay-human ledger edits (close 9475 umbrella, tick parked-orphan REVIEW_ME) verified genuine; suite 28 green, gaming-scan/roadmap-lint/cross-ledger/relay-doctor all clean; no code changes; routine_open=0

## 2026-06-26 10:16 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm-pdf: ledger-only window (TODO conformance prose relocation id:3441/c095); gaming-scan/roadmap-lint/todo-conformance clean; only open item id:8aa4 data-gated [HARD — meeting]; routine_open=0

## 2026-07-02 00:15 — reviewer (claude-fable-5, relay-loop)

Fable recheck (genuine Fable 5) of idle window: 28/28 green rerun, gaming-scan+doctor clean, cd59/1a30 audits confirm genuine; contract pointer v4→v6; id:8aa4 still data-gated; routine_open=0 [id:cd59,1a30,8aa4]

## 2026-07-02 08:49 — reviewer (claude-fable-5, relay-loop)

review zkm-pdf: EMPTY window (HEAD==relay-ckpt-20260702-0015) — classifier misfire, 3rd path-override drop this run (already routed:0537/3715); 28/28 green, gaming-scan/lint/cross-ledger/doctor clean, pointer v6 current; only open item id:8aa4 data-gated [HARD — meeting]; routine_open=0
