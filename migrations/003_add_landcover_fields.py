"""Add landcover analysis columns to risk_evaluation table."""


def migrate(db):
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_dense_veg INTEGER")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_sparse_veg INTEGER")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_bare INTEGER")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_built INTEGER")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_water INTEGER")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_radius_m INTEGER DEFAULT 500")
    db.execute_sql("ALTER TABLE risk_evaluation ADD COLUMN landcover_analyzed_at DATETIME")
