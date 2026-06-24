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
import os
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
    # Exactly one reasoned skip-log entry. id:1a30 superseded the terminal
    # "encrypted" reason with the self-draining-queue value "encrypted-pending"
    # (no md/CAS/inbox artifacts is unchanged — this is still a graceful skip).
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "encrypted-pending"
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


# ── id:1a30 — decryption queue + .eml password source ────────────────────────
#
# Owner decision (2026-06-13, ARCHITECTURE.md § Error philosophy): non-empty-
# password PDFs move from terminal reason "encrypted" to a self-draining queue
# (reason "encrypted-pending"). When the originating .eml carries the password
# in plaintext, the next run finds it, decrypts, and imports normally. No
# config surface, no key store. Empty-user-password behaviour (id:58d7) is
# unchanged.

def _deposit_inbox_pdf_from_eml(
    store: Path, pdf_bytes: bytes, *, eml_message: str, eml_body: str
) -> None:
    """Simulate zkm-eml: write PDF to mail CAS, attach an `eml` producer whose
    `message` points at an eml .md file (which we also write with `eml_body`),
    and create the flat inbox symlink. Mirrors
    test_convert.py::test_convert_inbox_pdf_attaches_to_existing_eml_cas.
    """
    from zkm.cas import write_object
    from zkm.sidecar import merge_producer

    cas_obj = write_object(store, "originals/mail", pdf_bytes)
    pdf_sha = cas_obj.parts[-2] + cas_obj.parts[-1]
    cas_sidecar = cas_obj.with_name(cas_obj.name + ".json")
    merge_producer(
        cas_sidecar,
        sha256=pdf_sha,
        producer={"plugin": "eml", "message": eml_message, "sha256": "e" * 64},
    )
    # The eml message file lives at <store>/<eml_message> and carries the body.
    eml_path = store / eml_message
    eml_path.parent.mkdir(parents=True, exist_ok=True)
    eml_path.write_text(eml_body, encoding="utf-8")

    inbox = store / "inbox"
    inbox.mkdir(exist_ok=True)
    rel_target = Path(os.path.relpath(cas_obj, inbox))
    (inbox / "locked.pdf").symlink_to(rel_target)


def _encrypted_pdf_bytes(*, user_password: str) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=str(TEXT_ONLY))
    writer.encrypt(user_password=user_password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_encrypted_pending_logged_no_artifacts(store, src):  # roadmap:1a30
    """A non-empty-password PDF with no recoverable password is logged
    `encrypted-pending` (not terminal `encrypted`) and leaves no store
    artifacts on the pending pass."""
    write_encrypted_pdf(src / "locked.pdf", user_password="secret")
    created = convert(store, cfg(src))
    assert created == []
    assert not list((store / "pdfs").rglob("*.md"))
    objects = store / "originals" / "pdfs" / "_objects"
    assert not objects.exists() or not any(f.is_file() for f in objects.rglob("*"))
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "encrypted-pending"


def test_encrypted_pending_idempotent_no_relog(store, src):  # roadmap:1a30
    """An unrecoverable encrypted-pending PDF re-attempted on a later run does
    not re-log (dedup key from id:2abf still holds)."""
    write_encrypted_pdf(src / "locked.pdf", user_password="secret")
    convert(store, cfg(src))
    convert(store, cfg(src))
    entries = read_skip_log(store)
    assert len(entries) == 1, f"pending entry re-logged: {entries}"
    assert entries[0]["reason"] == "encrypted-pending"


def test_eml_password_self_drains_pending_queue(store):  # roadmap:1a30
    """An inbox PDF encrypted with a non-empty user password whose originating
    .eml carries that password in plaintext is decrypted and imported."""
    pdf_bytes = _encrypted_pdf_bytes(user_password="hunter2")
    _deposit_inbox_pdf_from_eml(
        store,
        pdf_bytes,
        eml_message="mail/messages/2024-01-01_invoice.md",
        eml_body="Hello,\n\nPlease find the invoice attached.\n"
        "The PDF password is: hunter2\n\nRegards",
    )
    created = convert(store, cfg())
    assert len(created) == 1, "eml-sourced password did not drain the queue"
    post = frontmatter.load(created[0])
    assert "extractable text" in post.content
    # The pending entry is the only skip-log line, and it must not block import.
    # (A self-drained item may keep its earlier pending log line — what matters
    # is the import happened and no NEW reason was logged for this run.)
    reasons = {e["reason"] for e in read_skip_log(store)}
    assert reasons <= {"encrypted-pending"}


def test_eml_without_password_stays_pending(store):  # roadmap:1a30
    """An inbox encrypted PDF whose .eml has no recoverable password stays
    pending (no import, one encrypted-pending entry)."""
    pdf_bytes = _encrypted_pdf_bytes(user_password="hunter2")
    _deposit_inbox_pdf_from_eml(
        store,
        pdf_bytes,
        eml_message="mail/messages/2024-01-01_invoice.md",
        eml_body="Hello,\n\nPlease find the invoice attached.\n\nRegards",
    )
    created = convert(store, cfg())
    assert created == []
    assert not list((store / "pdfs").rglob("*.md"))
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "encrypted-pending"


# ── id:1a30 (follow-up) — broaden the password token boundary ─────────────────
# DECIDED 2026-06-16 (/relay human): a password may legitimately END in `!.,;:?`.
# The current trailing-`.,;:!?` rstrip in _scan_passwords truncates such a
# password (e.g. `Secret!` -> `Secret`), so a labelled password whose final
# character is punctuation never decrypts. Broaden the token: delimit only on
# whitespace / quotes / brackets; do not strip internal-or-final password
# punctuation. (Trailing punctuation that is clearly a sentence ender directly
# adjacent to nothing else is the only acceptable trim, and the labelled-only
# bias means a stray decrypt try is harmless even if a sentence comma sneaks in.)
def test_eml_password_with_trailing_punctuation_drains_queue(store):  # roadmap:1a30
    """A labelled password whose final char is punctuation (e.g. `Secret!`)
    must be recovered WHOLE and used to decrypt — not truncated to `Secret`."""
    pdf_bytes = _encrypted_pdf_bytes(user_password="Secret!")
    _deposit_inbox_pdf_from_eml(
        store,
        pdf_bytes,
        eml_message="mail/messages/2024-01-01_invoice.md",
        eml_body="Hi,\n\nThe PDF password is: Secret!\n\nRegards",
    )
    created = convert(store, cfg())
    assert len(created) == 1, (
        "trailing-punctuation password was truncated; the broadened token "
        "boundary must keep `Secret!` whole so the queue drains"
    )


def test_eml_password_with_internal_punctuation_is_recovered(store):  # roadmap:1a30
    """Passwords containing internal punctuation (!, .) are recovered whole.

    REVIEW_ME.md id:1a30 decision (c) 2026-06-16: broaden the token boundary —
    delimit on whitespace/quotes/brackets only; strip trailing sentence punctuation
    (.,;:?) but NOT trailing `!` so that passwords like `SecurePass!123` quoted
    mid-prose (`password is: SecurePass!123.`) are recovered as `SecurePass!123`
    — the sentence period is dropped but `!` stays mid-token, not truncated to
    `SecurePass`. A bare "drop all trailing strip" approach would instead keep
    the period (`SecurePass!123.`) and fail to decrypt.
    """
    password = "SecurePass!123"
    pdf_bytes = _encrypted_pdf_bytes(user_password=password)
    _deposit_inbox_pdf_from_eml(
        store,
        pdf_bytes,
        eml_message="mail/messages/2024-01-01_invoice.md",
        # Trailing period after the token (sentence context): must not eat into
        # `SecurePass!123` — only the `.` is stripped, `!` stays mid-token.
        eml_body=f"Hello,\n\nThe PDF password is: {password}.\n\nRegards",
    )
    created = convert(store, cfg())
    assert len(created) == 1, (
        f"password with internal punctuation ({password!r}) was not recovered whole"
    )


# ── id:cd59 — adopt shared zkm.pdftext helper for scanned-only routing ────────
#
# The cross-plugin drift risk (id:9475/02bd): zkm-pdf's local `min_text_chars`
# comparison counted text differently than `zkm.pdftext.probe` (strip semantics).
# This item wires zkm-pdf to the same shared oracle so both plugins can never
# disagree on whether a PDF is scanned-only.
#
# Also: `pdf_text_threshold` becomes the canonical config key; `min_text_chars`
# stays as a deprecated alias for one release.

def test_cd59_routing_uses_shared_pdftext_helper(store, src):  # roadmap:cd59
    """zkm-pdf's scanned-only routing must agree with the shared zkm.pdftext oracle.

    Concretely: resolve_threshold must read `pdf_text_threshold` from the config
    dict (canonical key); is_scanned_only must govern the skip decision; and the
    verdict must match what zkm.pdftext.probe+is_scanned_only compute directly.

    The discriminating case: set `pdf_text_threshold` to a value (10000) that
    exceeds TEXT_ONLY's char count, with NO `min_text_chars` key. If convert()
    still uses the shared pdftext.resolve_threshold, text_only.pdf will be
    skipped (below_threshold). If convert() ignores `pdf_text_threshold` and
    reads only `min_text_chars`, it uses the hardcoded default (100) instead
    and imports text_only.pdf — proving the key isn't wired.
    """
    import pypdf

    from zkm.pdftext import probe, is_scanned_only, resolve_threshold

    # Verify fixture premise: TEXT_ONLY has fewer than 10000 stripped chars.
    reader = pypdf.PdfReader(str(TEXT_ONLY))
    oracle_probe = probe(reader)
    high_threshold = 10000
    oracle_scanned_only = is_scanned_only(oracle_probe, high_threshold)
    assert oracle_scanned_only, (
        f"fixture premise broken — text_only.pdf has {oracle_probe.total_chars} "
        "stripped chars, expected < 10000 for this test"
    )

    shutil.copy(TEXT_ONLY, src / "text_only.pdf")
    config_canonical = {
        "source_dir": str(src),
        "pdf_text_threshold": high_threshold,
        # No `min_text_chars` key — the canonical key alone must govern the decision.
    }
    created = convert(store, config_canonical)
    assert created == [], (
        "pdf_text_threshold key was not used by convert(); text_only.pdf was "
        "imported when it should be scanned-only at the high threshold. "
        "Wire zkm.pdftext.resolve_threshold into convert()."
    )
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "below_threshold"


def test_cd59_min_text_chars_deprecated_alias(store, src):  # roadmap:cd59
    """min_text_chars still works as a deprecated alias for one release.

    When only `min_text_chars` is set (no `pdf_text_threshold`), the threshold
    is honoured — existing configs keep working.
    """
    shutil.copy(IMAGE_ONLY, src / "image_only.pdf")
    config_legacy = {
        "source_dir": str(src),
        "min_text_chars": 100,
        # No `pdf_text_threshold` — legacy key must be the fallback.
    }
    created = convert(store, config_legacy)
    assert created == [], "image_only.pdf should still be skipped via legacy min_text_chars key"
    entries = read_skip_log(store)
    assert len(entries) == 1
    assert entries[0]["reason"] == "below_threshold"
