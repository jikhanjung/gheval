# HANDOFF — Project Status for Session Continuity

> Maintained for continuity across sessions.
> Updated after each completed task. Read this first after a new session or context compact.

**Last updated**: 2026-02-13

---

## Current Project State

GHEval v0.1.0 — core features implemented, usable state.

### Completed Features
- PyQt6 + Leaflet.js map (OSM/Esri satellite tiles)
- GeoHeritageSite CRUD (in-place editing, auto-save)
- Satellite screenshot capture
- Road distance measurement (Overpass API, road type filtering)
- Satellite land cover analysis (OpenCV)
- Summer imagery Wayback auto-search
- Satellite imagery capture date display
- Coordinate parser (DMS/DDM/Decimal/space-separated)
- Risk evaluation (road_proximity + vegetation_cover, 2 criteria)
- Photo gallery
- PyInstaller build setup
- Site list in bottom panel layout

### Devlog Status
- P01–P04: completed (initial design, satellite analysis, Wayback, capture date)
- Work records 001–014: completed
- **P05 Phase 1**: PDF coordinate extraction — **implemented** (work record 014)

---

## Next Task: PDF Coordinate Extraction Phase 2+ (P05)

**Plan document**: `devlog/20260213_P05_PDF_화석발견지_좌표추출.md`

### Completed (Phase 1)
- PyMuPDF text extraction + regex coordinate scanning (6 formats incl. Korean DMS)
- PdfImportDialog with batch processing, review table, import to DB
- Menu integration: File > Import from PDF... (Ctrl+I)
- Files: `GhPdfExtractor.py` (new), `GhCommons.py`, `GhDialogs.py`, `GhEval.py`

### Remaining Phases
- **Phase 2** — Scanned PDF OCR (pytesseract, Korean+English)
- **Phase 3** — spaCy NER place name extraction + Nominatim geocoding
- **Phase 4** — PDF map image extraction + Leaflet overlay

---

## Known Issues / Notes

- (none currently)
