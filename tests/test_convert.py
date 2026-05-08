"""Tests for zkm-pdf convert.py."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import frontmatter
import pytest

from convert import PLUGIN_NAME, PLUGIN_VERSION, convert

FIXTURES = Path(__file__).parent / "fixtures"
TEXT_ONLY = FIXTURES / "text_only.pdf"
SPARSE_TEXT = FIXTURES / "sparse_text.pdf"
IMAGE_ONLY = FIXTURES / "image_only.pdf"
NODATE = FIXTURES / "nodate.pdf"


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
        "PDF_SOURCE_DIR": str(src_dir) if src_dir else "",
        "PDF_MIN_TEXT_CHARS": str(min_chars),
    }


# ── 1. Happy path ─────────────────────────────────────────────────────────────

def test_convert_creates_md_with_frontmatter(store, src):
    import shutil
    shutil.copy(TEXT_ONLY, src / "text_only.pdf")
    created = convert(store, cfg(src))
    assert len(created) == 1
    md = created[0]
    assert md.exists()
    # Path structure: pdfs/YYYY/MM/<date>_<slug>.md
    assert md.parts[-4] == "pdfs"
    post = frontmatter.load(md)
    assert post.metadata["source"] == PLUGIN_NAME
    assert post.metadata["processor"] == PLUGIN_NAME
    assert post.metadata["processor_version"] == PLUGIN_VERSION
    assert post.metadata["date"].startswith("2024-08-15")
    assert post.metadata["tags"] == []
    assert isinstance(post.metadata["sha256"], str) and len(post.metadata["sha256"]) == 64
    assert post.metadata["original"].startswith("originals/pdfs/_objects/")
    assert post.metadata["title"] == "Test Document Title"
    assert post.metadata["author"] == "Test Author Name"
    assert post.metadata["pages"] == 2
    assert post.metadata["text_chars"] >= 100
    # Body contains original link and extracted text
    assert "[original PDF](" in post.content
    assert "extractable text" in post.content


# ── 2. Idempotency ────────────────────────────────────────────────────────────

def test_convert_idempotent(store, src):
    import shutil
    shutil.copy(TEXT_ONLY, src / "text_only.pdf")
    first = convert(store, cfg(src))
    assert len(first) == 1

    cas_dir = store / "originals" / "pdfs" / "_objects"
    cas_before = sum(1 for f in cas_dir.rglob("*") if f.is_file())

    second = convert(store, cfg(src))
    assert second == []
    cas_after = sum(1 for f in cas_dir.rglob("*") if f.is_file())
    assert cas_after == cas_before


# ── 3. SHA-256 dedup across source paths ──────────────────────────────────────

def test_convert_dedup_by_sha256(store, src):
    import shutil
    shutil.copy(TEXT_ONLY, src / "copy_a.pdf")
    shutil.copy(TEXT_ONLY, src / "copy_b.pdf")
    created = convert(store, cfg(src))
    assert len(created) == 1
    cas_files = list((store / "originals" / "pdfs" / "_objects").rglob("*"))
    # Count only CAS objects (not .json sidecars) — one per unique sha256
    assert sum(1 for f in cas_files if f.is_file() and f.suffix != ".json") == 1


# ── 4. mtime fallback when /CreationDate is absent ───────────────────────────

def test_convert_no_creation_date_falls_back_to_mtime(store, src):
    import os
    import shutil

    # nodate.pdf has text but no /Info /CreationDate — forces mtime fallback
    dest = src / "nodate.pdf"
    shutil.copy(NODATE, dest)
    os.utime(dest, (1_700_000_000, 1_700_000_000))  # 2023-11-14T...
    created = convert(store, cfg(src))
    assert len(created) == 1
    post = frontmatter.load(created[0])
    assert post.metadata["date"].startswith("2023-")


# ── 5. Non-PDF files are skipped ─────────────────────────────────────────────

def test_convert_skips_non_pdf(store, src):
    import shutil
    shutil.copy(TEXT_ONLY, src / "real.pdf")
    (src / "notes.txt").write_text("ignore me")
    (src / "photo.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    created = convert(store, cfg(src))
    assert len(created) == 1


# ── 6. Empty source → no-op ───────────────────────────────────────────────────

def test_convert_no_op_on_empty_source(store, src):
    created = convert(store, cfg(src))
    assert created == []


# ── 7. Scanned-only PDF is silently skipped ───────────────────────────────────

def test_convert_skips_scanned_only_pdf(store, src):
    import shutil
    shutil.copy(IMAGE_ONLY, src / "image_only.pdf")
    created = convert(store, cfg(src))
    assert created == []
    # No pdfs md, no CAS, no sidecar
    assert not list((store / "pdfs").rglob("*.md"))
    assert not list((store / "originals" / "pdfs" / "_objects").rglob("*") if
                    (store / "originals" / "pdfs" / "_objects").exists() else [])


# ── 8. Threshold configurable; audit log written on skip ──────────────────────

def test_convert_threshold_configurable(store, src):
    import shutil
    shutil.copy(SPARSE_TEXT, src / "sparse.pdf")

    # Default threshold (100) → skip + log
    created = convert(store, cfg(src, min_chars=100))
    assert created == []
    log = store / ".zkm-state" / "zkm-pdf-skipped.jsonl"
    assert log.exists()
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["text_chars"] < 100
    assert entry["threshold"] == 100

    # Lowered threshold → passes, no new log line
    before_lines = len(lines)
    created2 = convert(store, cfg(src, min_chars=1))
    assert len(created2) == 1
    # sha is now in existing_shas for the second run — audit log unchanged
    lines_after = log.read_text().strip().splitlines()
    assert len(lines_after) == before_lines


# ── 9. Path collision → _1 suffix ────────────────────────────────────────────

def test_convert_path_collision_suffix(store, src):
    import re
    text_bytes = TEXT_ONLY.read_bytes()
    # Two distinct PDFs with same date and slug: mutate last byte
    (src / "text_only.pdf").write_bytes(text_bytes)
    (src / "text-only.pdf").write_bytes(text_bytes[:-1] + bytes([text_bytes[-1] ^ 0x01]))
    created = convert(store, cfg(src))
    assert len(created) == 2
    names = {p.name for p in created}
    suffixed = [n for n in names if re.search(r"_\d+\.md$", n)]
    assert len(suffixed) == 1


# ── 10. Canonical inbox symlink (PDF_SOURCE_DIR path) ────────────────────────

def test_convert_canonical_inbox_symlink(store, src):
    import shutil
    shutil.copy(TEXT_ONLY, src / "text_only.pdf")
    convert(store, cfg(src))
    inbox_pdfs = store / "inbox" / "pdfs"
    symlinks = [f for f in inbox_pdfs.iterdir() if f.is_symlink()]
    assert len(symlinks) == 1
    link = symlinks[0]
    target = Path(os.readlink(link))
    resolved = (link.parent / target).resolve()
    assert resolved.exists()
    sidecar_path = inbox_pdfs / (link.name + ".origin.json")
    assert sidecar_path.exists()
    data = json.loads(sidecar_path.read_text())
    assert any(p["plugin"] == PLUGIN_NAME for p in data["producers"])


# ── 11. Multi-producer sidecar (inbox-sourced PDF, PDF_SOURCE_DIR path) ──────

def test_convert_multi_producer_sidecar(store, src):
    import shutil
    from zkm.cas import write_object
    from zkm.inbox import symlink_with_sidecar

    pdf_bytes = TEXT_ONLY.read_bytes()
    # Simulate zkm-eml depositing the PDF into CAS and inbox (flat, as eml does today)
    cas_obj = write_object(store, "originals/pdfs", pdf_bytes)
    inbox_dir = store / "inbox"
    inbox_dir.mkdir(exist_ok=True)
    index: dict = {}
    eml_sha256 = "a" * 64
    symlink_with_sidecar(
        cas_object=cas_obj,
        link_dir=inbox_dir,
        link_name="invoice.pdf",
        producer={"plugin": "eml", "message": "mail/messages/2024-08-15_invoice.md", "sha256": eml_sha256},
        canonical_index=index,
    )
    assert len(list(inbox_dir.rglob("*.origin.json"))) == 1

    # Run zkm-pdf via PDF_SOURCE_DIR path with the same bytes (different source path)
    shutil.copy(TEXT_ONLY, src / "invoice.pdf")
    created = convert(store, cfg(src))
    assert len(created) == 1

    # CAS sidecar from _process_pdf (not the inbox sidecar) has pdf producer
    # For PDF_SOURCE_DIR, CAS sidecar is at originals/pdfs/_objects/.../...json
    pdf_cas_dir = store / "originals" / "pdfs" / "_objects"
    cas_sidecars = list(pdf_cas_dir.rglob("*.json"))
    assert len(cas_sidecars) >= 1
    plugins_seen = set()
    for sc_path in cas_sidecars:
        data = json.loads(sc_path.read_text())
        for p in data.get("producers", []):
            plugins_seen.add(p["plugin"])
    assert PLUGIN_NAME in plugins_seen


# ── 12. Primary path: inbox PDF attaches to existing eml CAS object ──────────

def test_convert_inbox_pdf_attaches_to_existing_eml_cas(store):
    """Primary flow: PDF deposited in inbox by zkm-eml gets processed."""
    from zkm.cas import write_object
    from zkm.sidecar import merge_producer

    # Simulate zkm-eml: write PDF bytes to mail CAS
    pdf_bytes = TEXT_ONLY.read_bytes()
    cas_obj = write_object(store, "originals/mail", pdf_bytes)
    pdf_sha = cas_obj.parts[-2] + cas_obj.parts[-1]  # sha256 from path
    eml_msg_sha = "b" * 64
    cas_sidecar = cas_obj.with_name(cas_obj.name + ".json")
    merge_producer(
        cas_sidecar,
        sha256=pdf_sha,
        producer={"plugin": "eml", "message": "mail/messages/2024-01-01_invoice.md", "sha256": eml_msg_sha},
    )

    # Simulate zkm-eml creating inbox symlink (flat, no .origin.json)
    inbox = store / "inbox"
    inbox.mkdir(exist_ok=True)
    rel_target = Path(os.path.relpath(cas_obj, inbox))
    (inbox / "invoice.pdf").symlink_to(rel_target)

    # Run zkm-pdf with no PDF_SOURCE_DIR
    created = convert(store, cfg())
    assert len(created) == 1
    md = created[0]

    # Frontmatter original must point at the existing mail CAS object
    post = frontmatter.load(md)
    assert post.metadata["original"].startswith("originals/mail/_objects/")

    # CAS sidecar now has both eml and pdf producers
    data = json.loads(cas_sidecar.read_text())
    plugins = {p["plugin"] for p in data["producers"]}
    assert "eml" in plugins
    assert PLUGIN_NAME in plugins

    # md lives under pdfs/YYYY/MM/
    assert md.parts[-4] == "pdfs"
