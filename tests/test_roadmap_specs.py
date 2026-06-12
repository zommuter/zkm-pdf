"""Red spec tests for ROADMAP.md items — the executor contract.

Each test is mapped to its roadmap item with a `# roadmap:XXXX` comment.
An item is done when its tests go green (plus a refactor pass), nothing else.

NOTE test_encrypted_empty_user_password_is_processed is a PINNING guard
(green pre-implementation): pypdf transparently decrypts empty-user-password
PDFs, and the id:58d7 implementation must not regress that by over-skipping
on a naive `is_encrypted` check.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import frontmatter
import pytest

from zkm_pdf.convert import convert

FIXTURES = Path(__file__).parent / "fixtures"
TEXT_ONLY = FIXTURES / "text_only.pdf"
IMAGE_ONLY = FIXTURES / "image_only.pdf"
MULTIPAGE_SPARSE = FIXTURES / "multipage_sparse.pdf"
META_RICH = FIXTURES / "meta_rich.pdf"


@pytest.fixture
def store(tmp_path: Path) -> Path:
    s = tmp_path / "store"
    (s / "pdfs").mkdir(parents=True)
    (s / "inbox").mkdir()
    (s / "originals" / "pdfs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(s)], check=True)
    return s


@pytest.fixture
def src(tmp_path: Path) -> Path:
    d = tmp_path / "pdf_src"
    d.mkdir()
    return d


def cfg(src_dir: Path | None = None, min_chars: int = 100) -> dict:
    return {
        "source_dir": str(src_dir) if src_dir else "",
        "min_text_chars": min_chars,
    }


def read_skip_log(store: Path) -> list[dict]:
    log = store / ".zkm-state" / "zkm-pdf-skipped.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().strip().splitlines()]


def write_encrypted_pdf(dest: Path, *, user_password: str, owner_password: str | None = None) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=str(TEXT_ONLY))
    writer.encrypt(user_password=user_password, owner_password=owner_password)
    buf = io.BytesIO()
    writer.write(buf)
    dest.write_bytes(buf.getvalue())


# ── id:2abf — skip-log reason field + cross-run dedup ─────────────────────────

def test_skip_log_reason_below_threshold(store, src):  # roadmap:2abf
    shutil.copy(IMAGE_ONLY, src / "image_only.pdf")
    created = convert(store, cfg(src))
    assert created == []
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "below_threshold"
    assert entries[0]["threshold"] == 100


def test_skip_log_no_duplicate_lines_across_runs(store, src):  # roadmap:2abf
    shutil.copy(IMAGE_ONLY, src / "image_only.pdf")
    convert(store, cfg(src))
    convert(store, cfg(src))  # unchanged store + source → must NOT re-log
    entries = read_skip_log(store)
    assert len(entries) == 1, (
        f"skip log grew to {len(entries)} lines across two identical runs; "
        "dedup key is (sha256, reason, threshold)"
    )


# ── id:58d7 — encrypted PDFs ──────────────────────────────────────────────────

def test_encrypted_pdf_skipped_with_reason(store, src):  # roadmap:58d7
    write_encrypted_pdf(src / "locked.pdf", user_password="secret")
    created = convert(store, cfg(src))
    assert created == []
    # No store artifacts at all
    assert not list((store / "pdfs").rglob("*.md"))
    objects = store / "originals" / "pdfs" / "_objects"
    assert not objects.exists() or not any(f.is_file() for f in objects.rglob("*"))
    assert not any((store / "inbox" / "pdfs").iterdir())
    # Exactly one reasoned skip-log entry
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "encrypted"
    assert len(entries[0]["sha256"]) == 64


def test_encrypted_empty_user_password_is_processed(store, src):  # roadmap:58d7 (pinning guard)
    write_encrypted_pdf(src / "restricted.pdf", user_password="", owner_password="ownerpw")
    created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert "extractable text" in post.content


# ── id:af0b — corrupt/malformed PDFs ─────────────────────────────────────────

def test_corrupt_pdf_skipped_with_reason_and_batch_continues(store, src):  # roadmap:af0b
    (src / "garbage.pdf").write_bytes(b"this is not a pdf at all" * 64)
    shutil.copy(TEXT_ONLY, src / "valid.pdf")
    created = convert(store, cfg(src))
    # The valid sibling is still imported
    assert len(created) == 1
    assert "valid" in created[0].name
    # The corrupt file leaves a reasoned log entry and no md
    entries = [e for e in read_skip_log(store) if e["path"].endswith("garbage.pdf")]
    assert len(entries) == 1
    assert entries[0]["reason"] == "error"


# ── id:1055 — threshold counts text chars, not page markers ─────────────────

def test_threshold_counts_text_chars_not_page_markers(store, src):  # roadmap:1055
    # Guard the fixture's premise using pypdf directly (independent of zkm_pdf):
    from pypdf import PdfReader

    reader = PdfReader(str(MULTIPAGE_SPARSE))
    page_texts = [(p.extract_text() or "").strip() for p in reader.pages]
    text_total = sum(len(t) for t in page_texts)
    marker_joined = "\n\n".join(
        f"<!-- page {i} -->\n\n{t}" for i, t in enumerate(page_texts, 1) if t
    )
    assert text_total < 100 < len(marker_joined), "fixture premise broken — regenerate"

    shutil.copy(MULTIPAGE_SPARSE, src / "multipage_sparse.pdf")
    created = convert(store, cfg(src, min_chars=100))
    assert created == [], (
        "PDF with only "
        f"{text_total} chars of page text passed the 100-char threshold on "
        "<!-- page N --> marker overhead"
    )


# ── id:03c2 — subject + keywords metadata into frontmatter ───────────────────

def test_subject_and_keywords_into_frontmatter(store, src):  # roadmap:03c2
    shutil.copy(META_RICH, src / "meta_rich.pdf")
    created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["subject"] == "Quarterly placeholder report"
    # /Keywords "Alpha, beta; GAMMA, alpha" → split on , and ;, strip, lowercase,
    # dedup order-preserving, merged into tags
    assert post.metadata["tags"] == ["alpha", "beta", "gamma"]
    # Existing metadata behavior unchanged
    assert post.metadata["title"] == "Meta Rich Title"
    assert post.metadata["author"] == "Meta Author"
    assert post.metadata["date"].startswith("2024-09-01")
