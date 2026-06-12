"""Build synthetic PDF test fixtures.

Run once to regenerate tests/fixtures/*.pdf:
    uv run python tests/build_fixtures.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def build_all() -> None:
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 not installed — run: uv sync --extra dev", file=sys.stderr)
        sys.exit(1)

    FIXTURES.mkdir(exist_ok=True)
    _build_text_only(FPDF)
    _build_sparse_text(FPDF)
    _build_image_only(FPDF)
    _build_nodate(FPDF)
    _build_multipage_sparse(FPDF)
    _build_meta_rich(FPDF)
    print(f"Built fixtures in {FIXTURES}")


def _build_text_only(FPDF) -> None:
    """A real text PDF with known metadata and substantial body text."""
    pdf = FPDF()
    pdf.set_title("Test Document Title")
    pdf.set_author("Test Author Name")
    pdf.set_creation_date(datetime(2024, 8, 15, 12, 30, 0))
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    # ~300 chars of body text on page 1
    pdf.multi_cell(
        0, 10,
        "This is a test document with extractable text content. " * 6,
    )
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Second page content. More text here for multi-page tests.")
    pdf.output(str(FIXTURES / "text_only.pdf"))


def _build_sparse_text(FPDF) -> None:
    """A PDF with only a handful of characters — below the default 100-char threshold."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Hi")  # 2 chars — well below threshold
    pdf.output(str(FIXTURES / "sparse_text.pdf"))


def _build_image_only(FPDF) -> None:
    """A PDF with no text layer at all (simulates a scanned-only PDF)."""
    pdf = FPDF()
    pdf.add_page()
    # Draw a colored rectangle — no text operators → pypdf extracts ""
    pdf.set_fill_color(200, 200, 200)
    pdf.rect(10, 10, 190, 270, "F")
    pdf.output(str(FIXTURES / "image_only.pdf"))


def _build_nodate(FPDF) -> None:
    """A text PDF with no /Info /CreationDate — for testing the mtime fallback."""
    import io
    from pypdf import PdfReader, PdfWriter

    # Create a text PDF via fpdf2, then strip its metadata dict via pypdf
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Testing mtime fallback for zkm-pdf. " * 8)
    raw = bytes(pdf.output())

    reader = PdfReader(io.BytesIO(raw))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    # Deliberately omit add_metadata() → no /Info /CreationDate

    buf = io.BytesIO()
    writer.write(buf)
    (FIXTURES / "nodate.pdf").write_bytes(buf.getvalue())


def _build_multipage_sparse(FPDF) -> None:
    """3 pages x ~30 chars each: total page TEXT < 100 chars, but the marker-joined
    body produced by _extract_text exceeds 100 — pins roadmap:1055 (threshold must
    count text chars only, not <!-- page N --> overhead)."""
    pdf = FPDF()
    pdf.set_creation_date(datetime(2024, 3, 3, 9, 0, 0))
    for _ in range(3):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Sparse page text, thirty char.")  # 30 chars
    pdf.output(str(FIXTURES / "multipage_sparse.pdf"))


def _build_meta_rich(FPDF) -> None:
    """Text PDF with /Subject and /Keywords metadata — for roadmap:03c2."""
    pdf = FPDF()
    pdf.set_title("Meta Rich Title")
    pdf.set_author("Meta Author")
    pdf.set_subject("Quarterly placeholder report")
    pdf.set_keywords("Alpha, beta; GAMMA, alpha")
    pdf.set_creation_date(datetime(2024, 9, 1, 8, 0, 0))
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Placeholder body text for metadata extraction tests. " * 4)
    pdf.output(str(FIXTURES / "meta_rich.pdf"))


if __name__ == "__main__":
    build_all()
