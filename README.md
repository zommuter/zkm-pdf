# zkm-pdf

zkm plugin that imports text-extractable PDF files into the knowledge store.

## What it does

- Scans `<store>/inbox/` for `.pdf` symlinks (deposited by `zkm-eml` or other plugins)
- Optionally walks an external `PDF_SOURCE_DIR` for direct PDF imports
- Extracts text via `pypdf`; emits `pdfs/YYYY/MM/<date>_<slug>.md` per PDF
- Silently skips scanned-only PDFs (no text layer) — leaves them for `zkm-scan`
- SHA-256 dedup: second run on the same content produces zero new files
- Merges a `pdf` producer into the existing CAS sidecar (multi-plugin provenance)

## Install

```bash
zkm plugin add ~/src/zkm-pdf
```

## Configuration (in `<store>/.env`)

| Variable | Default | Description |
|---|---|---|
| `PDF_SOURCE_DIR` | *(empty)* | Optional external directory to scan recursively for `.pdf` files |
| `PDF_MIN_TEXT_CHARS` | `100` | Min extracted chars to emit md. Below this → silently skip (provisional heuristic) |

## Output

```
pdfs/YYYY/MM/<date>_<slug>.md
originals/pdfs/_objects/<aa>/<rest>   # for PDF_SOURCE_DIR imports only
inbox/pdfs/<name>.pdf                 # for PDF_SOURCE_DIR imports only
<store>/.zkm-state/zkm-pdf-skipped.jsonl  # audit log of skipped PDFs
```

## Development

```bash
uv sync --extra dev
uv run python tests/build_fixtures.py  # regenerate fixtures after changing build_fixtures.py
uv run pytest
```
