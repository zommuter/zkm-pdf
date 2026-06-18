# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

## Items

- [x] Add `reason` field to the skip log and stop duplicate lines across runs [ROUTINE] <!-- id:2abf -->
  - **Acceptance**: every entry in `<store>/.zkm-state/zkm-pdf-skipped.jsonl`
    carries a `reason` key (`"below_threshold"` for the existing min-chars skip;
    ids 58d7/af0b add `"encrypted"` / `"error"`). Re-running `convert()` over a
    store whose skipped PDFs are unchanged appends NO new lines — dedup key is
    `(sha256, reason, threshold)`, so a re-run with a *different* threshold may
    log again. Existing log files without `reason` must not crash the dedup read.
  - **Tests**: `tests/test_roadmap_specs.py::test_skip_log_reason_below_threshold`,
    `::test_skip_log_no_duplicate_lines_across_runs` (each `# roadmap:2abf`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap_specs.py -k skip_log`
  - **Context**: `src/zkm_pdf/convert.py::_log_skipped` (single append-only
    writer; add a read-before-append dedup or an in-run loaded set). See
    ARCHITECTURE.md § Dedup and idempotency — the re-extraction cost stays,
    only the log noise goes. Keep JSONL (one object per line).

- [x] Handle encrypted PDFs: empty-password decrypt, else reasoned skip [ROUTINE] <!-- id:58d7 -->
  - **Acceptance**: a PDF encrypted with a non-empty user password is skipped
    gracefully — no md, no CAS object, no inbox symlink, one skip-log entry with
    `reason: "encrypted"`; the run continues and exits 0. A PDF encrypted with
    an EMPTY user password (owner-password-only protection, common for
    print/copy-restricted invoices) is transparently decrypted and imported
    normally. No password configuration is added.
  - **Tests**: `tests/test_roadmap_specs.py::test_encrypted_pdf_skipped_with_reason`
    (`# roadmap:58d7`) (currently RED);
    `::test_encrypted_empty_user_password_is_processed` is a PINNING guard
    (green today — pypdf already transparently decrypts empty-user-password
    PDFs; it must STAY green, i.e. don't over-skip on a naive `is_encrypted`)
  - **Done-check**: `uv run pytest tests/test_roadmap_specs.py -k encrypted`
  - **Context**: `src/zkm_pdf/convert.py::_extract_text` / `_get_pdf_meta`
    currently swallow the pypdf decrypt error into "0 chars" → misleading
    below-threshold skip. Check `PdfReader.is_encrypted`, try `decrypt("")`;
    on failure short-circuit BEFORE any store write (mirror the existing
    extract-before-write ordering in the source_dir path). Depends on the
    `reason` field from id:2abf — land that first or in the same session.

- [x] Handle corrupt/malformed PDFs: reasoned skip, batch continues [ROUTINE] <!-- id:af0b -->
  - **Acceptance**: a file that pypdf cannot parse at all (garbage bytes,
    truncated xref) produces one skip-log entry with `reason: "error"`, leaves
    no store artifacts, and does NOT abort the batch — sibling valid PDFs in the
    same run are still imported. Exit status of `convert()` stays normal
    (returns the valid PDFs' md paths).
  - **Tests**: `tests/test_roadmap_specs.py::test_corrupt_pdf_skipped_with_reason_and_batch_continues`
    (`# roadmap:af0b`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap_specs.py -k corrupt`
  - **Context**: same code paths as id:58d7; distinguish "could not parse"
    (`reason: "error"`) from "parsed, no text" (`reason: "below_threshold"`).
    Depends on the `reason` field from id:2abf.

- [x] Count only extracted text chars against the threshold, not page markers [ROUTINE] <!-- id:1055 -->
  - **Acceptance**: the `min_text_chars` comparison uses the sum of per-page
    extracted text lengths only — the `<!-- page N -->` markers and join
    separators that `_extract_text` adds to the md body are excluded. A
    multi-page sparse PDF whose total page text is below the threshold is
    skipped even when markers would push the rendered body above it. The
    frontmatter `text_chars` field reports the same text-only count.
  - **Tests**: `tests/test_roadmap_specs.py::test_threshold_counts_text_chars_not_page_markers`
    (`# roadmap:1055`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap_specs.py -k page_markers`
  - **Context**: `src/zkm_pdf/convert.py::_extract_text` returns the marker-joined
    body; the cleanest fix returns `(body, text_char_count)` (or a small
    dataclass) so `_emit_md`/the source_dir pre-check compare the right number.
    Interpretation pinned in REVIEW_ME.md. Fixture
    `tests/fixtures/multipage_sparse.pdf` (regen via `tests/build_fixtures.py`).

- [x] Extract PDF subject and keywords metadata into frontmatter [ROUTINE] <!-- id:03c2 -->
  - **Acceptance**: when the PDF `/Info` dict carries `/Subject`, frontmatter
    gains `subject: <stripped string>`; when it carries `/Keywords`, the
    keywords are split on `,` and `;`, stripped, lowercased, deduped
    (order-preserving) and merged into the existing `tags:` list. Absent
    metadata adds no keys (no empty `subject:`); existing title/author/date
    behavior is unchanged.
  - **Tests**: `tests/test_roadmap_specs.py::test_subject_and_keywords_into_frontmatter`
    (`# roadmap:03c2`) (currently RED)
  - **Done-check**: `uv run pytest tests/test_roadmap_specs.py -k subject_and_keywords`
  - **Context**: `src/zkm_pdf/convert.py::_get_pdf_meta` (pypdf exposes
    `metadata.subject` / `metadata.keywords`) and the `fm` dict in `_emit_md`.
    keywords→tags mapping is a judgment call — see REVIEW_ME.md. Fixture
    `tests/fixtures/meta_rich.pdf` (regen via `tests/build_fixtures.py`).

- [x] Decryption queue for non-empty-password PDFs + .eml password source [HARD — strong model] <!-- id:1a30 -->
  - **Done** (relay HARD, 2026-06-15): non-empty-password PDFs now log
    `reason: "encrypted-pending"` (was terminal `"encrypted"`) with no
    md/CAS/inbox artifacts; on the inbox path the originating `.eml` (CAS
    sidecar `eml` producer `message`) is scanned for a labelled plaintext
    password and tried as a decrypt key, so the queue self-drains next run.
    Empty-user-password (id:58d7) unchanged; dedup (id:2abf) keeps pending
    entries from re-logging. No config, no key store (owner directive).
    Tests: `tests/test_roadmap_specs.py` `test_encrypted_pending_logged_no_artifacts`,
    `test_encrypted_pending_idempotent_no_relog`,
    `test_eml_password_self_drains_pending_queue`,
    `test_eml_without_password_stays_pending` (all green). Password-regex
    interpretation pinned in REVIEW_ME.md. Impl: `convert.py`
    `_recover_passwords_from_eml`/`_scan_passwords` + `_extract_text(passwords=)`.
  - **Why HARD**: changes the encrypted-PDF outcome from terminal skip to a
    self-draining queue, and wires a NEW cross-source link (the originating
    `.eml` as a password source) — touches the import-ordering contract, the
    skip-log semantics (new `reason: "encrypted-pending"`), and the inbox/CAS
    attach path that already binds PDFs to their `.eml`. Mis-handling risks
    storing plaintext passwords or importing a doc twice (once pending, once
    decrypted). Owner directive: keep it lightweight until the email-password
    link proves its worth — NO config surface, NO key store yet.
  - **Acceptance**: a PDF with a non-empty user password is logged with
    `reason: "encrypted-pending"` (not terminal `"encrypted"`) and leaves no
    md/CAS/inbox artifacts on the pending pass; when a password becomes known
    the entry is re-attempted and imported normally, and the pending entry no
    longer re-logs (dedup key from id:2abf still holds). The originating `.eml`
    (already linked in the inbox-PDF→eml-CAS attach path) is scanned for a
    plaintext password and tried automatically so the queue self-drains. Empty
    user password behaviour (id:58d7) is unchanged. No password config/key store.
  - **Tests**: new RED specs in `tests/test_roadmap_specs.py` (`# roadmap:1a30`)
    covering: encrypted-pending logging, no-artifact-on-pending, eml-derived
    password self-drain, and idempotent re-run.
  - **Context**: extends the id:58d7 short-circuit in
    `src/zkm_pdf/convert.py::_extract_text`/`_get_pdf_meta`; reuse the inbox
    PDF→eml CAS linkage (see `tests/test_convert.py::test_convert_inbox_pdf_attaches_to_existing_eml_cas`)
    for the password-source. Originated as an owner decision on the id:58d7
    REVIEW_ME box (2026-06-13). Low expected volume — favour the simplest queue
    that works (a `reason` value + re-scan on next run), defer any store.

- [x] Broaden the eml password-token boundary so trailing punctuation isn't truncated [ROUTINE] <!-- id:1a30 -->
  - **Origin**: reverse-handoff of the /relay human decision 2026-06-16 on the
    id:1a30 REVIEW_ME box (parts a/b confirmed; part c — token boundary — needs a
    code change). REUSES the existing id:1a30 token (single-id-two-views): the
    HARD queue work shipped, this is the follow-up the human review surfaced.
  - **Why ROUTINE**: a self-contained tweak to `_scan_passwords` /
    `_PASSWORD_TOKEN_RE` in `src/zkm_pdf/convert.py` (~line 283/295) plus one
    test — no new cross-source link, no config, no key store.
  - **Problem**: `_scan_passwords` does `candidate.rstrip(".,;:!?")` (convert.py:295),
    so a labelled password whose final character is one of those (e.g. `Secret!`)
    is truncated to `Secret` and never decrypts. Mid-token punctuation already
    survives (`SecurePass!123` is kept whole); only the *trailing* trim is the bug.
  - **Acceptance**: a labelled password ending in punctuation (`Secret!`,
    `pass.word`, `pin:1234?`) is recovered WHOLE and used as a decrypt key, so an
    inbox encrypted PDF whose `.eml` carries such a password self-drains the
    pending queue. Delimit the token only on whitespace / quotes / brackets
    (`_PASSWORD_TOKEN_RE` already does this); drop or narrow the trailing
    `rstrip(".,;:!?")` so legitimate final password punctuation is preserved.
    Labelled-only bias (id:1a30 part a) means a rare over-greedy decrypt try is
    harmless. Empty-user-password (id:58d7) and dedup (id:2abf) unchanged.
  - **Done-check**: `tests/test_roadmap_specs.py::test_eml_password_with_trailing_punctuation_drains_queue`
    (RED today, `# roadmap:1a30`) goes green; all other tests stay green.
  - **Test**: red spec already in place —
    `test_eml_password_with_trailing_punctuation_drains_queue` (uses
    `_encrypted_pdf_bytes(user_password="Secret!")` + an `.eml` body `password is: Secret!`).

- [ ] Calibrate or replace the min-text "scanned-only" heuristic [HARD — strong model] <!-- id:9475 -->
  - **DECIDED 2026-06-18 (/meeting --cross gated-HARD triage) — SUBSUMED into zkm-scan id:02bd.**
    Do NOT recalibrate this threshold in isolation (that reintroduces the cross-plugin drift bug
    02bd exists to fix — today the two plugins compute the count differently, so a whitespace-heavy
    PDF can be skipped by BOTH = processed by neither). Unified decision: extract ONE `zkm.pdftext`
    core helper returning a canonical char count (use zkm-pdf's `.strip()`+skip-empty-pages
    semantics, id:1055-reviewed), consumed by BOTH plugins via a single shared `pdf_text_threshold`
    key → drift impossible by construction. **Discriminator: PILOT a per-page density / text-coverage
    ratio (more robust on sparse many-page PDFs); fall back to the evidence-backed char-count default
    if the pilot doesn't beat it on the skip-log corpus** (`zkm-pdf-skipped.jsonl`, id:2abf). Keep
    zkm-scan's `min_text_chars=10` OCR-junk floor a SEPARATE key. Coordinated build under id:02bd.
    See `dotclaude-skills/docs/meeting-notes/2026-06-18-1219-cross-gated-hard-triage.md`.
  - **Why HARD**: the 100-char default was an explicit provisional judgment
    ("revisit before Session 13") with no corpus evidence. Choosing the
    discriminator (chars-per-page density? text-coverage ratio? embedded-font
    presence?) and its default requires evaluating against a real PDF corpus
    and coordinating the boundary with zkm-scan's intake — a misclassification
    silently routes documents to the wrong pipeline in both directions.
  - **Acceptance**: a documented decision (ARCHITECTURE.md) backed by
    measurements over a real corpus (the skip log from id:2abf is the intended
    evidence source); either a recalibrated default with rationale or a new
    per-page-density heuristic behind the same config surface; plugin.yaml
    `NOTE: provisional` removed; `zkm-pdf-skipped.jsonl` false-skip rate
    reported. Coordinate with zkm-scan before changing the boundary.
