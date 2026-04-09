"""
init_db.py — Initialize the database and seed default admin user.
Run once: python init_db.py
"""
from app import create_app
from models import db, User, SystemSettings
from sqlalchemy import inspect, text


def ensure_expenses_schema(engine):
    insp = inspect(engine)
    if 'expenses' not in insp.get_table_names():
        return

    cols = [c['name'] for c in insp.get_columns('expenses')]
    if 'category' not in cols:
        return

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

    print('✅  Expenses table schema upgraded (removed obsolete category column).')

app = create_app()

with app.app_context():
    db.create_all()
    ensure_expenses_schema(db.engine)
    print("✅  Database tables created.")

    # Seed admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            name='System Administrator',
            email='admin@sonnac.lk',
            username='admin',
            role='admin',
            is_active=True,
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅  Default admin user created  →  username: admin  /  password: admin123")
    else:
        print("ℹ️   Admin user already exists, skipped.")

    # Seed default settings
    if not SystemSettings.query.first():
        settings = SystemSettings(
            company_name='Sonnac Lanka Enterprises',
            company_address='No. 1, Main Street, Colombo 03, Sri Lanka',
            company_phone='+94 11 234 5678',
            company_email='info@sonnac.lk',
            default_currency='LKR',
            tax_rate=0.0,
            quote_prefix='SLE-QT',
            invoice_prefix='SLE-INV',
            pi_prefix='SLE-PI',
            terms_conditions=(
                "1. Prices are subject to change without prior notice.\n"
                "2. A non-refundable deposit is required to reserve the vehicle.\n"
                "3. Full payment must be completed before delivery.\n"
                "4. All vehicles are sold as-is unless otherwise stated in writing.\n"
                "5. This quotation is valid for 7 days from the date of issue."
            ),
        )
        db.session.add(settings)
        db.session.commit()
        print("✅  Default system settings created.")
    else:
        print("ℹ️   System settings already exist, skipped.")

    print("\n🚀  Ready! Run the app with:  python app.py")
    print("    Admin portal: http://127.0.0.1:5000/auth/login")
    print("    Public site:  http://127.0.0.1:5000/")
