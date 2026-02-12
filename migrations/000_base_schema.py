"""Initial base schema migration."""

from peewee import SqliteDatabase


def migrate(db):
    """Create base tables if they don't exist."""
    cursor = db.execute_sql("""
        CREATE TABLE IF NOT EXISTS geoheritage_site (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_name VARCHAR(255) NOT NULL,
            site_desc TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address VARCHAR(255),
            site_type VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS site_screenshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL REFERENCES geoheritage_site(id) ON DELETE CASCADE,
            file_path VARCHAR(255) NOT NULL,
            map_type VARCHAR(50) DEFAULT 'HYBRID',
            zoom_level INTEGER DEFAULT 15,
            scale_info VARCHAR(255),
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            note TEXT
        )
    """)

    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS risk_evaluation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL REFERENCES geoheritage_site(id) ON DELETE CASCADE,
            screenshot_id INTEGER REFERENCES site_screenshot(id) ON DELETE SET NULL,
            road_proximity INTEGER DEFAULT 1,
            accessibility INTEGER DEFAULT 1,
            vegetation_cover INTEGER DEFAULT 1,
            development_signs INTEGER DEFAULT 1,
            overall_risk INTEGER DEFAULT 4,
            risk_level VARCHAR(50) DEFAULT 'LOW',
            evaluator_notes TEXT,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS site_photo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL REFERENCES geoheritage_site(id) ON DELETE CASCADE,
            file_path VARCHAR(255) NOT NULL,
            photo_type VARCHAR(255),
            description TEXT,
            taken_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
