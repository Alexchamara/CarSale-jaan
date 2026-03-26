"""One-off helper to add logistics_tax column to cost_sheets.

Usage (after activating venv):
  FLASK_APP=app:create_app python upgrade_costing_tax.py

Safe to re-run; skips if the column already exists.
"""
from app import create_app
from models import db
from sqlalchemy import inspect, text


def ensure_column(engine):
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('cost_sheets')}
    if 'logistics_tax' in cols:
        print('ℹ️  logistics_tax already exists, skipped.')
        return

    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE cost_sheets ADD COLUMN logistics_tax FLOAT DEFAULT 0'))
    print('✅ Added logistics_tax column to cost_sheets.')


def main():
    app = create_app()
    with app.app_context():
        ensure_column(db.engine)
        print('🚀 Cost sheet tax upgrade complete.')


if __name__ == '__main__':
    main()
