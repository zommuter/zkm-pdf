# zkm-pdf architecture

Design decisions with rationale and rejected alternatives. Code lives in
`src/zkm_pdf/convert.py`; this file explains *why* it looks the way it does.

## Position in the zkm pipeline

```
zkm-eml ──deposits .pdf attachments──▶ inbox/ ──▶ zkm-pdf ──▶ pdfs/YYYY/MM/*.md ──▶ index
                         (CAS symlinks)               │
external source_dir ──────────────────────────────────┘
                                                       └─ no text layer? → skip,
                                                          log, leave for zkm-scan
```

zkm-pdf is a **source plugin** (writes md bodies), not an amender. It is also a
**downstream consumer**: its primary input is CAS objects another plugin
(zkm-eml) already wrote.

## Two input paths (decided at v0.4.0)

1. **Inbox path (primary)** — walk `<store>/inbox/**/*.pdf` symlinks, resolve to
   the CAS object, **reuse it** (no byte copy), merge a `pdf` producer into the
   *existing* CAS sidecar. Frontmatter `original:` points at the upstream CAS
   path (e.g. `originals/mail/_objects/...`).
2. **`source_dir` path (optional)** — walk an external directory, write a *new*
   CAS object under `originals/pdfs/`, create the canonical `inbox/pdfs/`
   symlink via `zkm.inbox.symlink_with_sidecar`.

**Rationale**: most PDFs arrive as mail attachments; duplicating their bytes
into a second CAS tree would break the one-object-per-sha256 invariant and
double storage. The external path exists for scanner-dump / Downloads-folder
imports that have no upstream plugin.

**Rejected**: a single unified path that always copies into `originals/pdfs/` —
violates CAS dedup and would orphan the eml producer chain.

## Ownership: the upstream allowlist

`docs/plugin-spec.md` requires plugins to be a **no-op on inbox items they do
not own**. A pure reading of "own" (only items whose sidecar lists *this*
plugin) would make the primary path impossible — eml-deposited PDFs list `eml`,
not `pdf`. zkm-pdf therefore interprets ownership via an explicit allowlist:

```python
_KNOWN_UPSTREAM_PLUGINS = {"eml", "pdf"}
```

An inbox PDF is processed only if its **CAS-object sidecar** (`<obj>.json`, not
the inbox `.origin.json`) lists a known upstream producer. Foreign deposits
(e.g. a future plugin's PDFs) are untouched and `convert()` returns `[]`.

**Rejected**: processing every inbox `*.pdf` regardless of producer — would
silently consume other plugins' staging artifacts and violate the spec contract.
**Rejected**: per-store config for the allowlist — no second upstream exists
yet; add config only when one appears (observe-before-preventing).

## Dedup and idempotency

The dedup key is the **SHA-256 of the PDF bytes**. Existing shas are discovered
by scanning `pdfs/**/*.md` frontmatter at the start of each run — the markdown
tree is the single source of truth; there is no separate state DB.

**Rejected**: a sha→md state file under `.zkm-state/` — would drift from the
store after manual `git rm` / `zkm rm` and contradicts core's "md is source of
truth" rule. The O(n) frontmatter scan is cheap at current store sizes.

Consequence (known wart): PDFs that were *skipped* (below threshold) never gain
an md, so they are re-extracted — and re-logged — on every run. Fixing the
re-log noise is ROADMAP id:2abf; the re-extraction cost is accepted until the
per-CAS-object extraction cache lands (core `docs/object-storage.md`, Phase 3+).

## Routing contract (id:cd59, shared with zkm-scan)

```
total_chars = Σ len(page.extract_text().strip()) over all pages
              (None from extract_text() contributes 0)

A PDF is scanned-only when total_chars < threshold (strict less-than).
A PDF at exactly the threshold is NOT scanned-only.
```

This contract is owned by `zkm.pdftext` (`src/zkm/pdftext.py` in the parent
repo) and consumed identically by both zkm-pdf and zkm-scan.  The authoritative
`probe`/`is_scanned_only`/`resolve_threshold` trio lives there; plugins must not
re-implement the measurement — import it to close the cross-plugin drift risk
(id:9475/02bd).

**Config key**: `pdf_text_threshold` (canonical, top-level, shared). The old
`min_text_chars` key is a deprecated alias for one release (id:cd59): if only
`min_text_chars` is set and `pdf_text_threshold` is absent, `convert()` promotes
it before calling `resolve_threshold`. Set `pdf_text_threshold` in new configs.

**Default**: 100 stripped characters (`zkm.pdftext.DEFAULT_TEXT_THRESHOLD`).

Skips are silent on stdout but always appended to
`<store>/.zkm-state/zkm-pdf-skipped.jsonl` (path, sha256, text_chars,
threshold, mtime) so the boundary is auditable and zkm-scan can later consume
the queue.

## Date and path scheme

`pdfs/YYYY/MM/<date>_<slug>.md`, slug from the source filename, `_N` suffix on
collisions. The date is resolved as:

1. PDF `/CreationDate` metadata (pypdf `creation_date`), ISO-8601-ified;
2. fallback: file mtime.

**Known limitation**: for the inbox path the "file" is the CAS object, whose
mtime is the *deposit* time, not the document time — acceptable because mail
attachments almost always carry `/CreationDate`, and the eml md already anchors
the mail date. Revisit only if real corpora show frequent metadata-less inbox
PDFs.

## Error philosophy (current state + direction)

Skip entries carry an explicit `reason` (id:2abf): `_extract_text` distinguishes
parse failures (`reason: "error"`, id:af0b — a bad file never aborts the batch;
siblings still import) from PDFs requiring a non-empty user password
(`reason: "encrypted-pending"`, id:58d7/id:1a30 — short-circuited before any
store write). Empty-user-password PDFs (owner-only/copy-restricted) are
transparently decrypted via `decrypt("")` and imported normally. A genuinely
text-light PDF stays `reason: "below_threshold"`. The skip log dedups on
`(sha256, reason, threshold)` so unchanged files don't re-log but threshold
experiments remain auditable. A conversion batch never aborts on one bad file.

### Self-draining decryption queue (id:1a30, owner decision 2026-06-13)

Non-empty-password PDFs are **not** terminally skipped: they are queued with
`reason: "encrypted-pending"`. On the inbox path (zkm-eml deposits), the
originating `.eml` message — located via the CAS sidecar's `eml` producer
`message` field (a store-relative path to the eml `.md`) — is scanned for a
plaintext password (`_recover_passwords_from_eml` → `_scan_passwords`). Any
labelled candidate ("password:/Passwort:/PIN/code is X") is tried as a decrypt
key, so the queue **self-drains on the next run** once the mail carrying the
password is imported. `_extract_text` always tries the empty password first
(keeps id:58d7 transparent), then the recovered candidates. The dedup key from
id:2abf keeps an unrecoverable pending entry from re-logging across runs.

Kept deliberately lightweight: **no config surface, no key store** — the only
state is the `encrypted-pending` log line, and the password regex is
conservative (labelled tokens only; a false negative just leaves the item
pending, never mis-imports). Source-dir PDFs have no eml link, so they queue as
pending but cannot self-drain until a future password source is wired in.
**Rejected** (per owner directive): a persistent password/key store, a config
key for user-supplied passwords, and unlabelled-token guessing — all deferred
until the email-password link proves its worth.

## Packaging (SB5, 2026-06)

Importable package `src/zkm_pdf/` with a `zkm.plugins` entry point (wheel
install path) **plus** a root `convert.py` shim + root `plugin.yaml`
(filesystem-discovery path for the dev-checkout workflow). Core's SB2 loader
injects `src/` onto `sys.path` before importing the shim. The duplication
(two `plugin.yaml`s, shim re-exports) is the price of supporting both install
origins; keep the copies byte-identical.

**Rejected**: dropping the root shim and requiring editable installs for dev —
core's filesystem discovery contract predates SB5 and other plugins rely on it.
