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
