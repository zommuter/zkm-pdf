# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_roadmap_specs.py::test_threshold_counts_text_chars_not_page_markers
  (roadmap:1055) — the min_text_chars threshold compares the SUM of per-page
  extracted text only; the `<!-- page N -->` markers and join separators are
  excluded (today they count, so a many-page sparse PDF passes on marker bytes).
  Note: the 100-char default itself remains provisional regardless — its
  calibration is the separate [HARD] item id:9475.

- [ ] tests/test_roadmap_specs.py::test_encrypted_pdf_skipped_with_reason +
  ::test_encrypted_empty_user_password_is_processed (roadmap:58d7) — encrypted
  PDFs with an EMPTY user password (owner-only protection, common for
  copy-restricted invoices) are imported; non-empty-password PDFs are skipped
  with reason "encrypted" and stay in the skip log (NOT handed to zkm-scan,
  which can't OCR them either). No password configuration surface is added.

- [ ] tests/test_roadmap_specs.py::test_skip_log_no_duplicate_lines_across_runs
  (roadmap:2abf) — skip-log dedup key is (sha256, reason, threshold): the same
  skipped PDF is never re-logged across runs at the same threshold, but
  changing min_text_chars logs a fresh line (so threshold experiments remain
  auditable).

- [ ] tests/test_roadmap_specs.py::test_subject_and_keywords_into_frontmatter
  (roadmap:03c2) — /Keywords is split on "," and ";", stripped, lowercased,
  deduped order-preserving, and merged into `tags:`; alternative of a separate
  verbatim `keywords:` frontmatter field was rejected (tags is zkm's only
  categorization field). /Subject becomes a `subject:` string field as-is.
