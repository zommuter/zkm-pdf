"""zkm-pdf — import text-extractable PDFs into the knowledge store.

Two input paths:
  1. inbox/ PDFs (symlinks deposited by zkm-eml or other plugins) — primary.
     Reuses the existing CAS object; merges a 'pdf' producer into its sidecar.
  2. Optional PDF_SOURCE_DIR — walks an external directory, writes new CAS
     objects under originals/pdfs/, creates inbox/pdfs/ symlinks.

Silently skips PDFs with < PDF_MIN_TEXT_CHARS extracted text (intended for
zkm-scan). Logs skipped items to <store>/.zkm-state/zkm-pdf-skipped.jsonl.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from zkm.atomic import write_atomic
from zkm.cas import write_object
from zkm.hashing import sha256_file
from zkm.inbox import build_canonical_index, symlink_with_sidecar
from zkm.sidecar import merge_producer, read_sidecar

PLUGIN_NAME = "pdf"
PLUGIN_VERSION = "0.4.0"

_KNOWN_UPSTREAM_PLUGINS = {"eml", PLUGIN_NAME}


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    """Import PDFs from inbox/ and optional PDF_SOURCE_DIR into store_path/pdfs/.

    Returns a list of paths to newly created .md files.
    progress: optional callback(current, total, message).
    """
    min_chars = int(config.get("min_text_chars", 100))
    src_dir_raw = str(config.get("source_dir", "") or "")

    (store_path / "pdfs").mkdir(parents=True, exist_ok=True)
    (store_path / "originals" / "pdfs").mkdir(parents=True, exist_ok=True)
    (store_path / "inbox" / "pdfs").mkdir(parents=True, exist_ok=True)

    existing_shas = _scan_existing_shas(store_path / "pdfs")
    created: list[Path] = []

    # ── Path 1: inbox-sourced PDFs (deposited by zkm-eml etc.) ───────────────
    inbox_candidates = _find_inbox_pdf_candidates(store_path)
    total = len(inbox_candidates)
    for i, (real_path, cas_sidecar) in enumerate(inbox_candidates, 1):
        if progress:
            progress(i, total, real_path.name)
        sha = sha256_file(real_path)
        if sha in existing_shas:
            continue
        md = _emit_md(
            store_path=store_path,
            pdf_path=real_path,
            sha=sha,
            cas_path=real_path,
            cas_sidecar=cas_sidecar,
            min_chars=min_chars,
        )
        if md:
            created.append(md)
            existing_shas.add(sha)

    # ── Path 2: optional external PDF_SOURCE_DIR ──────────────────────────────
    if src_dir_raw:
        src = Path(src_dir_raw).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"source_dir does not exist: {src}")
        src_candidates = sorted(f for f in src.rglob("*.pdf") if f.is_file())
        canonical_index = build_canonical_index(store_path, "inbox/pdfs")
        inbox_pdfs_dir = store_path / "inbox" / "pdfs"
        total2 = len(src_candidates)
        for i, pdf_file in enumerate(src_candidates, 1):
            if progress:
                progress(i, total2, pdf_file.name)
            sha = sha256_file(pdf_file)
            if sha in existing_shas:
                continue
            # Extract text before touching the store so skips leave no traces.
            text = _extract_text(pdf_file)
            if len(text) < min_chars:
                _log_skipped(store_path, pdf_file, sha, len(text), min_chars)
                continue
            cas_path = write_object(store_path, "originals/pdfs", pdf_file)
            cas_sidecar = cas_path.with_name(cas_path.name + ".json")
            symlink_with_sidecar(
                cas_object=cas_path,
                link_dir=inbox_pdfs_dir,
                link_name=pdf_file.name.lower(),
                producer={"plugin": PLUGIN_NAME, "message": str(pdf_file), "sha256": sha},
                canonical_index=canonical_index,
            )
            md = _emit_md(
                store_path=store_path,
                pdf_path=pdf_file,
                sha=sha,
                cas_path=cas_path,
                cas_sidecar=cas_sidecar,
                min_chars=min_chars,
                preextracted_text=text,
            )
            if md:
                created.append(md)
                existing_shas.add(sha)

    return created


# ── Core md-emit helper ───────────────────────────────────────────────────────

def _emit_md(
    *,
    store_path: Path,
    pdf_path: Path,
    sha: str,
    cas_path: Path,
    cas_sidecar: Path,
    min_chars: int,
    preextracted_text: str | None = None,
) -> Path | None:
    """Extract text, write md, update CAS sidecar. Returns md path or None on skip."""
    text = preextracted_text if preextracted_text is not None else _extract_text(pdf_path)

    if len(text) < min_chars:
        _log_skipped(store_path, pdf_path, sha, len(text), min_chars)
        return None

    meta = _get_pdf_meta(pdf_path)
    date_str = _pdf_date_to_iso(meta.get("creation_date")) or _mtime_iso(pdf_path)
    date_prefix = date_str[:10]
    year, month = date_prefix[:4], date_prefix[5:7]

    pdfs_dir = store_path / "pdfs" / year / month
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(pdf_path.stem)
    out = _unique_path(pdfs_dir, date_prefix, slug)

    original_rel = str(cas_path.relative_to(store_path))

    fm: dict = {
        "source": PLUGIN_NAME,
        "processor": PLUGIN_NAME,
        "processor_version": PLUGIN_VERSION,
        "date": date_str,
        "tags": [],
        "sha256": sha,
        "original": original_rel,
        "pages": meta.get("pages", 0),
        "text_chars": len(text),
    }
    if meta.get("title"):
        fm["title"] = meta["title"]
    if meta.get("author"):
        fm["author"] = meta["author"]

    rel_link = os.path.relpath(cas_path, out.parent)
    body = f"[original PDF]({rel_link})\n\n{text}\n"
    write_atomic(out, frontmatter.dumps(frontmatter.Post(body, **fm)))

    merge_producer(
        cas_sidecar,
        sha256=sha,
        producer={"plugin": PLUGIN_NAME, "message": str(out.relative_to(store_path)), "sha256": sha},
    )

    return out


# ── Inbox discovery helpers ───────────────────────────────────────────────────

def _find_inbox_pdf_candidates(store_path: Path) -> list[tuple[Path, Path]]:
    """Return (real_pdf_path, cas_sidecar_path) for owned inbox PDFs.

    'Owned' means the CAS sidecar lists at least one known upstream plugin
    (eml, pdf), satisfying the plugin-spec no-op-on-unowned contract.
    """
    inbox = store_path / "inbox"
    if not inbox.exists():
        return []
    results: list[tuple[Path, Path]] = []
    seen_real: set[str] = set()
    for link in sorted(inbox.rglob("*.pdf")):
        if not link.is_symlink():
            continue
        try:
            real = link.resolve()
        except OSError:
            continue
        if not real.is_file():
            continue
        key = str(real)
        if key in seen_real:
            continue
        seen_real.add(key)
        cas_sidecar = real.with_name(real.name + ".json")
        if not _is_owned(cas_sidecar):
            continue
        results.append((real, cas_sidecar))
    return results


def _is_owned(cas_sidecar: Path) -> bool:
    """Return True if this CAS object was produced by a known upstream plugin."""
    data = read_sidecar(cas_sidecar)
    if not data:
        return False
    return any(p.get("plugin") in _KNOWN_UPSTREAM_PLUGINS for p in data.get("producers", []))


# ── PDF metadata / extraction ─────────────────────────────────────────────────

def _get_pdf_meta(path: Path) -> dict:
    """Return dict with: title, author, pages, creation_date (all optional)."""
    result: dict = {}
    try:
        reader = PdfReader(str(path))
        result["pages"] = len(reader.pages)
        meta = reader.metadata
        if meta:
            if meta.title:
                result["title"] = str(meta.title).strip()
            if meta.author:
                result["author"] = str(meta.author).strip()
            if meta.creation_date:
                result["creation_date"] = meta.creation_date
    except (PdfReadError, Exception):  # noqa: BLE001
        pass
    return result


def _extract_text(path: Path) -> str:
    """Extract all text from PDF, pages separated by <!-- page N --> markers."""
    try:
        reader = PdfReader(str(path))
        parts = []
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(f"<!-- page {i} -->\n\n{text}")
        return "\n\n".join(parts)
    except (PdfReadError, Exception):  # noqa: BLE001
        return ""


def _pdf_date_to_iso(dt: object) -> str | None:
    """Convert a pypdf metadata date (datetime or None) to ISO 8601 string."""
    if dt is None:
        return None
    try:
        if hasattr(dt, "isoformat"):
            if getattr(dt, "tzinfo", None) is None:
                return dt.isoformat(timespec="seconds")  # type: ignore[union-attr]
            return dt.astimezone().isoformat(timespec="seconds")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
    return None


def _log_skipped(
    store_path: Path, pdf_path: Path, sha: str, text_chars: int, threshold: int
) -> None:
    state_dir = store_path / ".zkm-state"
    state_dir.mkdir(exist_ok=True)
    entry = json.dumps({
        "path": str(pdf_path),
        "sha256": sha,
        "text_chars": text_chars,
        "threshold": threshold,
        "mtime": pdf_path.stat().st_mtime,
    })
    log_path = state_dir / "zkm-pdf-skipped.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(entry + "\n")


# ── Store helpers ─────────────────────────────────────────────────────────────

def _scan_existing_shas(directory: Path) -> set[str]:
    shas: set[str] = set()
    for md in directory.rglob("*.md"):
        try:
            post = frontmatter.load(md)
            sha = post.metadata.get("sha256")
            if isinstance(sha, str):
                shas.add(sha)
        except Exception:  # noqa: BLE001
            continue
    return shas


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).astimezone().isoformat(
        timespec="seconds"
    )


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "document"


def _unique_path(directory: Path, date_prefix: str, slug: str) -> Path:
    candidate = directory / f"{date_prefix}_{slug}.md"
    i = 1
    while candidate.exists():
        candidate = directory / f"{date_prefix}_{slug}_{i}.md"
        i += 1
    return candidate
