import os
import logging
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from PyQt6.QtCore import QThread, pyqtSignal

from GhCommons import scan_coordinates_in_text

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────

@dataclass
class ExtractedSite:
    latitude: float
    longitude: float
    matched_text: str
    source_pdf: str
    page_number: int
    context: str
    site_name: str = ""


@dataclass
class PdfResult:
    filename: str
    filepath: str
    page_count: int = 0
    sites: list = field(default_factory=list)
    error: str = ""
    warnings: list = field(default_factory=list)


@dataclass
class BatchResult:
    results: list = field(default_factory=list)

    @property
    def total_sites(self):
        return sum(len(r.sites) for r in self.results)

    @property
    def successful_count(self):
        return sum(1 for r in self.results if not r.error)

    @property
    def failed_count(self):
        return sum(1 for r in self.results if r.error)


# ── PDF text extraction ──────────────────────────────────

def extract_text_from_pdf(filepath):
    """Extract text from a PDF file. Returns list of (page_num, text, is_scanned)."""
    pages = []
    doc = fitz.open(filepath)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text", sort=True)
            is_scanned = len(text.strip()) < 50 and len(page.get_images()) > 0
            pages.append((page_num + 1, text, is_scanned))
    finally:
        doc.close()
    return pages


def _extract_context(text, match_text, context_chars=50):
    """Extract surrounding context around a matched coordinate string."""
    idx = text.find(match_text)
    if idx == -1:
        return match_text
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(match_text) + context_chars)
    snippet = text[start:end].strip()
    snippet = " ".join(snippet.split())  # normalize whitespace
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


# ── Single PDF processing ────────────────────────────────

def process_single_pdf(filepath):
    """Process one PDF file. Returns PdfResult."""
    filename = os.path.basename(filepath)
    basename = os.path.splitext(filename)[0]
    result = PdfResult(filename=filename, filepath=filepath)

    try:
        pages = extract_text_from_pdf(filepath)
        result.page_count = len(pages)
    except Exception as e:
        result.error = str(e)
        return result

    scanned_pages = []
    all_sites = []

    for page_num, text, is_scanned in pages:
        if is_scanned:
            scanned_pages.append(page_num)
            continue

        coords = scan_coordinates_in_text(text)
        for lat, lng, matched in coords:
            context = _extract_context(text, matched)
            site = ExtractedSite(
                latitude=lat,
                longitude=lng,
                matched_text=matched,
                source_pdf=filename,
                page_number=page_num,
                context=context,
            )
            all_sites.append(site)

    # Deduplicate across pages (same coords from different pages)
    seen = set()
    unique_sites = []
    for site in all_sites:
        key = (round(site.latitude, 4), round(site.longitude, 4))
        if key not in seen:
            seen.add(key)
            unique_sites.append(site)

    # Auto-generate site names
    for i, site in enumerate(unique_sites, 1):
        if len(unique_sites) == 1:
            site.site_name = basename
        else:
            site.site_name = f"{basename} - Site {i}"

    result.sites = unique_sites

    if scanned_pages:
        result.warnings.append(
            f"Scanned pages detected ({len(scanned_pages)}): "
            f"pages {', '.join(str(p) for p in scanned_pages[:5])}"
            f"{'...' if len(scanned_pages) > 5 else ''} — OCR not yet supported"
        )

    if not unique_sites:
        result.warnings.append("No coordinates found in this PDF")

    return result


# ── Batch processing worker ──────────────────────────────

class PdfProcessorWorker(QThread):
    """Background worker for processing multiple PDFs."""

    progress = pyqtSignal(int, int, str)       # current, total, filename
    file_completed = pyqtSignal(object)         # PdfResult
    all_completed = pyqtSignal(object)          # BatchResult
    error_occurred = pyqtSignal(str)

    def __init__(self, pdf_paths, parent=None):
        super().__init__(parent)
        self.pdf_paths = pdf_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        batch = BatchResult()
        total = len(self.pdf_paths)

        for i, path in enumerate(self.pdf_paths):
            if self._cancelled:
                break

            filename = os.path.basename(path)
            self.progress.emit(i + 1, total, filename)

            try:
                result = process_single_pdf(path)
            except Exception as e:
                logger.exception(f"Error processing {path}")
                result = PdfResult(
                    filename=filename,
                    filepath=path,
                    error=str(e),
                )

            batch.results.append(result)
            self.file_completed.emit(result)

        self.all_completed.emit(batch)


# ── Utility ──────────────────────────────────────────────

def collect_pdf_paths(paths):
    """Collect .pdf file paths from a mix of files and directories. Returns sorted list."""
    pdf_paths = []
    for path in paths:
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            pdf_paths.append(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        pdf_paths.append(os.path.join(root, f))
    return sorted(set(pdf_paths))
