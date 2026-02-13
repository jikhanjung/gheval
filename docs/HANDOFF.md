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
- Work records 001–013: completed
- **P05**: PDF fossil site coordinate extraction — **plan document written, implementation not started**

---

## Next Task: PDF Fossil Site Coordinate Extraction (P05)

**Plan document**: `devlog/20260213_P05_PDF_화석발견지_좌표추출.md`

### Summary
Extract fossil discovery site coordinates from geology/paleontology PDF papers automatically.

### Implementation Phases
1. **Phase 1 (MVP)** — PyMuPDF text extraction + regex coordinate scanning + review UI + batch processing
2. **Phase 2** — Scanned PDF OCR (pytesseract, Korean+English)
3. **Phase 3** — spaCy NER place name extraction + Nominatim geocoding
4. **Phase 4** — PDF map image extraction + Leaflet overlay

### Pre-start Checklist
- [ ] Confirm starting with Phase 1
- [ ] Confirm PyMuPDF AGPL license is acceptable
- [ ] Prepare sample test PDFs

### New Files (planned)
- `GhPdfExtractor.py` — PDF processing module
- `PdfImportDialog` in `GhDialogs.py`
- `scan_coordinates_in_text()` in `GhCommons.py`

### New Dependencies (planned)
- PyMuPDF (~30MB)
- pytesseract + Pillow (Phase 2, ~30MB native)
- spaCy + ko_core_news_lg (Phase 3, ~500MB, optional)

---

## Known Issues / Notes

- (none currently)
