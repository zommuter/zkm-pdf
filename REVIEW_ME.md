# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] tests/test_roadmap_specs.py::test_threshold_counts_text_chars_not_page_markers
  (roadmap:1055) — the min_text_chars threshold compares the SUM of per-page
  extracted text only; the `<!-- page N -->` markers and join separators are
  excluded (today they count, so a many-page sparse PDF passes on marker bytes).
  Note: the 100-char default itself remains provisional regardless — its
  calibration is the separate [HARD] item id:9475.
