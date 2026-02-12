"""Add road_distance column to risk_evaluation table."""


def migrate(db):
    db.execute_sql("""
        ALTER TABLE risk_evaluation
        ADD COLUMN road_distance REAL
    """)
