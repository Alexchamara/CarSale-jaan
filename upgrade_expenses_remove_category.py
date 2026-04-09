"""One-off helper to remove obsolete category column from expenses.

Usage (after activating venv):
  python upgrade_expenses_remove_category.py

Safe to re-run; skips if schema is already updated.
"""
from app import create_app
from models import db
from sqlalchemy import inspect, text


TARGET_COLUMNS = [
    'id',
    'expense_date',
    'description',
    'amount',
    'payment_method',
    'created_at',
]


def migrate_sqlite(engine):
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE expenses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date DATE NOT NULL,
                description TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_method VARCHAR(20) NOT NULL,
                created_at DATETIME
            )
        '''))
        conn.execute(text('''
            INSERT INTO expenses_new (id, expense_date, description, amount, payment_method, created_at)
            SELECT id, expense_date, description, amount, payment_method, created_at
            FROM expenses
        '''))
        conn.execute(text('DROP TABLE expenses'))
        conn.execute(text('ALTER TABLE expenses_new RENAME TO expenses'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_expenses_expense_date ON expenses(expense_date)'))


def migrate_non_sqlite(engine):
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE expenses DROP COLUMN category'))


def ensure_expenses_schema(engine):
    insp = inspect(engine)
    if 'expenses' not in insp.get_table_names():
        print('ℹ️  expenses table not found, skipped.')
        return

    cols = [c['name'] for c in insp.get_columns('expenses')]
    col_set = set(cols)

    if 'category' not in col_set:
        print('ℹ️  expenses schema already updated, skipped.')
        return

    missing_required = [c for c in TARGET_COLUMNS if c not in col_set]
    if missing_required:
        print(f'❌ Cannot migrate: missing expected columns {missing_required}')
        return

    if engine.dialect.name == 'sqlite':
        migrate_sqlite(engine)
    else:
        migrate_non_sqlite(engine)

    print('✅ Removed obsolete category column from expenses.')


def main():
    app = create_app()
    with app.app_context():
        ensure_expenses_schema(db.engine)
        print('🚀 Expenses schema upgrade complete.')


if __name__ == '__main__':
    main()
