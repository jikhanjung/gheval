# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Handoff

**At the start of every new session, read `docs/HANDOFF.md` first to understand current project state.**
It tracks in-progress work, next tasks, and known issues.
Update HANDOFF.md whenever a task is completed to keep it current.

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

2 criteria (1-5 each): road_proximity, vegetation_cover
Sum (2-10) → LOW(2-4), MODERATE(5-6), HIGH(7-8), CRITICAL(9-10)

## Data Storage

App data stored in `data/` directory next to the executable (or `main.py` in dev):
- `gheval.db` — SQLite database
- `screenshots/` — Map screenshot PNGs
- `photos/` — Imported site photos

## Documentation (devlog/)

Every non-trivial task must be documented in `devlog/`:

### Plan Documents (before work)
- **Format**: `YYYYMMDD_P##_{title}.md`
- **Naming**: P01, P02, P03... (sequential per project)
- **Contents**: Context, approach, affected files, implementation steps

### Work Records (after work)
- **Format**: `YYYYMMDD_###_{title}.md`
- **Naming**: 001, 002, 003... (sequential, continuing from last)
- **Contents**: What changed, why, key decisions, modified files summary

### When to skip
- Trivial bug fixes (typo, one-liner)
- Documentation-only changes

### Workflow
1. Create P document → plan the work
2. Implement
3. Create numbered document → record what was done
