"""Add road_snap_lat/lng columns to risk_evaluation table."""


def migrate(db):
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN road_snap_lat REAL")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN road_snap_lng REAL")
