# zkm-pdf

[zkm](https://github.com/zommuter/zkm) plugin that imports text-extractable PDF files into the knowledge store.

## What it does

- Scans `<store>/inbox/` for `.pdf` symlinks (deposited by `zkm-eml` or other plugins)
- Optionally walks an external `source_dir` for direct PDF imports
- Extracts text via `pypdf`; emits `pdfs/YYYY/MM/<date>_<slug>.md` per PDF
- Skips scanned-only PDFs (no text layer) — leaves them for `zkm-scan`; every skip is
  logged with a `reason` to `<store>/.zkm-state/zkm-pdf-skipped.jsonl`
- Handles encrypted PDFs: empty-user-password PDFs decrypt transparently; non-empty
  ones queue as `encrypted-pending` and self-drain when the originating `.eml` carries
  a plaintext password
- SHA-256 dedup: second run on the same content produces zero new files
- Merges a `pdf` producer into the existing CAS sidecar (multi-plugin provenance)

## Install

Clone this repo inside your zkm `plugins/` directory:

```bash
git clone https://github.com/zommuter/zkm-pdf.git plugins/zkm-pdf
```

## Configuration (in `<store>/zkm-config.yaml`, plugin section `pdf`)

| Key | Default | Description |
|---|---|---|
| `source_dir` | *(empty)* | Optional external directory to scan recursively for `.pdf` files |
| `pdf_text_threshold` | `100` | Min stripped extracted chars to treat a PDF as text-extractable; below this → scanned-only, logged to `zkm-pdf-skipped.jsonl`, left for zkm-scan. Shared with zkm-scan via `zkm.pdftext` (set once at the top level). |
| `min_text_chars` | `100` | **Deprecated** alias for `pdf_text_threshold` (honoured one release when the canonical key is absent). Prefer `pdf_text_threshold`. |

## Output

```
pdfs/YYYY/MM/<date>_<slug>.md
originals/pdfs/_objects/<aa>/<rest>   # for source_dir imports only
inbox/pdfs/<name>.pdf                 # for source_dir imports only
<store>/.zkm-state/zkm-pdf-skipped.jsonl  # audit log of skipped PDFs
```

## Development

```bash
cd plugins/zkm-pdf
uv sync --extra dev
uv run python tests/build_fixtures.py  # regenerate fixtures after changing build_fixtures.py
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE)
