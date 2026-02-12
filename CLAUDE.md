# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

GeoHeritage Evaluator (GHEval) — a PyQt6 desktop application for evaluating geoheritage site degradation risk using satellite/map imagery. Uses OSM + Leaflet.js for maps with Esri World Imagery for satellite views.

## Architecture

- **Flat file structure** — all Python files at project root, following DikeFinder patterns
- **Peewee ORM** with SQLite (`db = SqliteDatabase(None)`, initialized at runtime)
- **QWebChannel** for bidirectional JS↔Python map communication
- **QSettings("PaleoBytes", "GHEval")** for window state persistence

## Key Files

- `main.py` — Entry point, logging setup, DB init
- `GhCommons.py` — Constants, paths (`resource_path()`, `get_data_dir()`), risk calculation
- `GhModels.py` — 4 Peewee models: GeoHeritageSite, SiteScreenshot, RiskEvaluation, SitePhoto
- `GhEval.py` — QMainWindow with splitter layout, all UI orchestration
- `GhComponents.py` — MapWidget, SiteListWidget, SiteInfoPanel, EvaluationPanel, PhotoGalleryWidget
- `GhDialogs.py` — SiteEditDialog, SettingsDialog, ReportDialog
- `GhMapBridge.py` — MapBridge QObject for QWebChannel
- `templates/map_view.html` — Leaflet.js + OSM/Esri tiles + QWebChannel JS

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

# Run migrations
python migrate.py
```

## Risk Calculation

4 criteria (1-5 each): road_proximity, accessibility, vegetation_cover, development_signs
Sum (4-20) → LOW(4-8), MODERATE(9-12), HIGH(13-16), CRITICAL(17-20)

## Data Storage

App data stored in `~/.gheval/` (Linux/Mac) or `%APPDATA%/.gheval/` (Windows):
- `gheval.db` — SQLite database
- `screenshots/` — Map screenshot PNGs
- `photos/` — Imported site photos
- `gheval.log` — Application log
