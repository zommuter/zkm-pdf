"""zkm-pdf — import text-extractable PDFs into the knowledge store.

Two input paths:
  1. inbox/ PDFs (symlinks deposited by zkm-eml or other plugins) — primary.
     Reuses the existing CAS object; merges a 'pdf' producer into its sidecar.
  2. Optional PDF_SOURCE_DIR — walks an external directory, writes new CAS
     objects under originals/pdfs/, creates inbox/pdfs/ symlinks.

Silently skips PDFs with < PDF_MIN_TEXT_CHARS extracted text (intended for
zkm-scan). Logs skipped items to <store>/.zkm-state/zkm-pdf-skipped.jsonl.
Skip reasons: "below_threshold", "encrypted-pending", "error".

Non-empty-password PDFs are not terminally skipped: they are queued with
reason "encrypted-pending" (id:1a30). When the PDF arrived via the inbox
(deposited by zkm-eml), the originating .eml message is scanned for a
plaintext password and tried automatically, so the queue self-drains on the
next run once the password is known. No password config surface, no key store
(owner directive, 2026-06-13). Source-dir PDFs have no eml link, so they stay
pending until a future password source is wired in.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
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


@dataclass
class _ExtractResult:
    """Result of PDF text extraction."""
    body: str          # marker-joined body for the .md file
    text_chars: int    # sum of per-page text lengths (markers excluded)
    encrypted: bool = False   # True when no candidate password decrypted it
    error: bool = False       # True when PDF cannot be parsed at all


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
            result = _extract_text(pdf_file)
            if result.error:
                _log_skipped(store_path, pdf_file, sha, 0, min_chars, reason="error")
                continue
            if result.encrypted:
                # No eml link on the source-dir path → no password source yet;
                # queue as pending rather than terminally skipping (id:1a30).
                _log_skipped(store_path, pdf_file, sha, 0, min_chars,
                             reason="encrypted-pending")
                continue
            if result.text_chars < min_chars:
                _log_skipped(store_path, pdf_file, sha, result.text_chars, min_chars,
                             reason="below_threshold")
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
                preextracted=result,
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
    preextracted: _ExtractResult | None = None,
) -> Path | None:
    """Extract text, write md, update CAS sidecar. Returns md path or None on skip."""
    if preextracted is not None:
        result = preextracted
    else:
        # Inbox path: recover candidate passwords from the originating .eml so a
        # non-empty-password PDF self-drains once the password is known (id:1a30).
        passwords = _recover_passwords_from_eml(store_path, cas_sidecar)
        result = _extract_text(pdf_path, passwords)

    if result.error:
        _log_skipped(store_path, pdf_path, sha, 0, min_chars, reason="error")
        return None
    if result.encrypted:
        _log_skipped(store_path, pdf_path, sha, 0, min_chars, reason="encrypted-pending")
        return None
    if result.text_chars < min_chars:
        _log_skipped(store_path, pdf_path, sha, result.text_chars, min_chars,
                     reason="below_threshold")
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
        "text_chars": result.text_chars,
    }
    if meta.get("title"):
        fm["title"] = meta["title"]
    if meta.get("author"):
        fm["author"] = meta["author"]
    if meta.get("subject"):
        fm["subject"] = meta["subject"]
    if meta.get("keywords"):
        # Merge keywords into tags: split on , and ;, strip, lowercase, dedup order-preserving
        raw_kw = re.split(r"[,;]", meta["keywords"])
        kw_list = list(dict.fromkeys(k.strip().lower() for k in raw_kw if k.strip()))
        fm["tags"] = kw_list

    rel_link = os.path.relpath(cas_path, out.parent)
    body = f"[original PDF]({rel_link})\n\n{result.body}\n"
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


# ── Password recovery from the originating .eml (id:1a30) ─────────────────────

# Conservative labelled-password patterns. A PDF password in mail is almost
# always introduced by an explicit label ("password: X", "Passwort: X", "PIN",
# "code"); we deliberately do NOT guess unlabelled tokens — a false positive
# would either fail to decrypt (harmless) or, worse, never (the queue just
# stays pending). The chosen token is the first non-space run after the label,
# trimmed of surrounding quotes/brackets and trailing sentence punctuation.
# This heuristic is a judgment call — see REVIEW_ME.md.
_PASSWORD_LABEL_RE = re.compile(
    r"(?:pdf[\s-]*)?(?:password|passwort|kennwort|pin|code|passcode)"
    r"\s*(?:is|ist|lautet|:|=|->|→)+\s*",
    re.IGNORECASE,
)
_PASSWORD_TOKEN_RE = re.compile(r"[^\s'\"`\[\]()<>]+")


def _scan_passwords(text: str) -> list[str]:
    """Return candidate passwords found after a password label, order-preserving
    and deduped. Empty list if none found."""
    found: list[str] = []
    for m in _PASSWORD_LABEL_RE.finditer(text):
        tail = text[m.end():]
        tok = _PASSWORD_TOKEN_RE.match(tail)
        if not tok:
            continue
        candidate = tok.group(0).rstrip(".,;:!?")
        if candidate:
            found.append(candidate)
    return list(dict.fromkeys(found))


def _recover_passwords_from_eml(store_path: Path, cas_sidecar: Path) -> list[str]:
    """Scan the originating .eml message (linked via the CAS sidecar's `eml`
    producer) for plaintext PDF passwords. Returns [] if there is no eml link,
    the message file is missing, or no labelled password is present.

    The `message` field of an `eml` producer is a store-relative path to the
    eml's markdown file (see zkm-eml's inbox deposit contract); we read that
    file's text and scan it. Anything unreadable degrades to no candidates —
    the PDF simply stays `encrypted-pending`.
    """
    data = read_sidecar(cas_sidecar)
    if not data:
        return []
    candidates: list[str] = []
    for producer in data.get("producers", []):
        if producer.get("plugin") != "eml":
            continue
        message = producer.get("message")
        if not message:
            continue
        eml_path = store_path / message
        try:
            text = eml_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidates.extend(_scan_passwords(text))
    return list(dict.fromkeys(candidates))


# ── PDF metadata / extraction ─────────────────────────────────────────────────

def _get_pdf_meta(path: Path) -> dict:
    """Return dict with: title, author, subject, keywords, pages, creation_date (all optional)."""
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
            subject = getattr(meta, "subject", None)
            if subject:
                result["subject"] = str(subject).strip()
            keywords = getattr(meta, "keywords", None)
            if keywords:
                result["keywords"] = str(keywords).strip()
    except (PdfReadError, Exception):  # noqa: BLE001
        pass
    return result


def _extract_text(path: Path, passwords: list[str] | None = None) -> _ExtractResult:
    """Extract all text from PDF, pages separated by <!-- page N --> markers.

    Returns an _ExtractResult with:
    - body: marker-joined content for the .md file
    - text_chars: sum of per-page extracted text lengths (markers excluded)
    - encrypted: True when the PDF requires a password none of `passwords` (nor
      the empty password) unlocks
    - error: True when the PDF cannot be parsed at all

    `passwords` is an ordered list of candidate passwords recovered from an
    external source (e.g. the originating .eml, id:1a30); the empty password is
    always tried first so owner-only-restricted PDFs (id:58d7) stay transparent.
    """
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            # Empty user password first (transparent for owner-only restrictions),
            # then any recovered candidate passwords (id:1a30 self-draining queue).
            candidates = [""] + list(passwords or [])
            if not any(reader.decrypt(pw) for pw in candidates):
                return _ExtractResult(body="", text_chars=0, encrypted=True)
        parts = []
        text_chars = 0
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                text_chars += len(text)
                parts.append(f"<!-- page {i} -->\n\n{text}")
        return _ExtractResult(body="\n\n".join(parts), text_chars=text_chars)
    except (PdfReadError, Exception):  # noqa: BLE001
        return _ExtractResult(body="", text_chars=0, error=True)


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
    store_path: Path,
    pdf_path: Path,
    sha: str,
    text_chars: int,
    threshold: int,
    *,
    reason: str,
) -> None:
    """Append a skip entry to the JSONL log, deduplicating on (sha256, reason, threshold).

    Existing entries without a 'reason' field are treated as unknown and do not
    block new entries from being written — this avoids crashing on legacy logs.
    """
    state_dir = store_path / ".zkm-state"
    state_dir.mkdir(exist_ok=True)
    log_path = state_dir / "zkm-pdf-skipped.jsonl"

    # Read existing entries to dedup; skip malformed lines gracefully.
    existing_keys: set[tuple[str, str, int]] = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                existing_keys.add((
                    obj.get("sha256", ""),
                    obj.get("reason", ""),
                    int(obj.get("threshold", 0)),
                ))
            except (json.JSONDecodeError, ValueError):
                continue

    key = (sha, reason, threshold)
    if key in existing_keys:
        return  # already logged with this (sha256, reason, threshold)

    entry = json.dumps({
        "path": str(pdf_path),
        "sha256": sha,
        "reason": reason,
        "text_chars": text_chars,
        "threshold": threshold,
        "mtime": pdf_path.stat().st_mtime,
    })
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
