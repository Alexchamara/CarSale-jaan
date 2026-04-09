from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access the admin panel.'
login_manager.login_message_category = 'warning'

# ─── Role Permissions ────────────────────────────────────────────────────────
ROLE_PERMISSIONS = {
    'admin': {
        'inventory': ['view', 'create', 'edit', 'delete'],
        'costing':   ['view', 'create', 'edit', 'delete'],
        'quotations':['view', 'create', 'edit', 'delete'],
        'sales':     ['view', 'create', 'edit', 'delete'],
        'customers': ['view', 'create', 'edit', 'delete'],
        'reports':   ['view'],
        'expenses':  ['view', 'create', 'edit', 'delete'],
        'users':     ['view', 'create', 'edit', 'delete'],
        'settings':  ['view', 'edit'],
    },
    'sales_manager': {
        # Full sales ops + can see financials/reports, no user admin
        'inventory': ['view', 'create', 'edit'],
        'costing':   ['view', 'create', 'edit'],
        'quotations':['view', 'create', 'edit', 'delete'],
        'sales':     ['view', 'create', 'edit', 'delete'],
        'customers': ['view', 'create', 'edit', 'delete'],
        'reports':   ['view'],
        'expenses':  ['view', 'create', 'edit'],
        'users':     ['view'],
    },
    'sales_executive': {
        # Front-line sales only — NO costing (hides margins), NO reports
        'inventory': ['view'],
        'quotations':['view', 'create', 'edit'],
        'sales':     ['view', 'create', 'edit'],
        'customers': ['view', 'create', 'edit'],
    },
    'accounts': {
        # Finance/admin — sees costs and invoices, NO sales pipeline editing
        'inventory': ['view'],
        'costing':   ['view', 'create', 'edit'],
        'quotations':['view', 'create', 'edit'],
        'sales':     ['view'],
        'customers': ['view'],
        'reports':   ['view'],
        'expenses':  ['view', 'create', 'edit', 'delete'],
    },
    'viewer': {
        # Read-only, inventory only
        'inventory': ['view'],
    },
}

# ─── User ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer')
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, module, action):
        perms = ROLE_PERMISSIONS.get(self.role, {})
        return action in perms.get(module, [])

    @property
    def role_label(self):
        labels = {
            'admin': 'Admin',
            'sales_manager': 'Sales Manager',
            'sales_executive': 'Sales Executive',
            'accounts': 'Accounts',
            'viewer': 'Viewer',
        }
        return labels.get(self.role, self.role.title())

# ─── Vehicle Meta Data ───────────────────────────────────────────────────────
class VehicleMake(db.Model):
    __tablename__ = 'vehicle_makes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    models = db.relationship('VehicleModel', backref='make', lazy=True, cascade='all, delete-orphan')


class VehicleModel(db.Model):
    __tablename__ = 'vehicle_models'
    id = db.Column(db.Integer, primary_key=True)
    make_id = db.Column(db.Integer, db.ForeignKey('vehicle_makes.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('make_id', 'name', name='uq_make_model'),)


# ─── Vehicle ──────────────────────────────────────────────────────────────────
class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    chassis_no = db.Column(db.String(50), unique=True)
    engine_no = db.Column(db.String(50))
    reg_no = db.Column(db.String(30))
    make_id = db.Column(db.Integer, db.ForeignKey('vehicle_makes.id'))
    model_id = db.Column(db.Integer, db.ForeignKey('vehicle_models.id'))
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    body_type = db.Column(db.String(30))
    fuel_type = db.Column(db.String(20))
    transmission = db.Column(db.String(20))
    color = db.Column(db.String(30))
    mileage = db.Column(db.Integer)
    condition_grade = db.Column(db.String(10))
    status = db.Column(db.String(20), default='available')
    description = db.Column(db.Text)
    internal_notes = db.Column(db.Text)
    is_archived = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    selling_price = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship('VehicleImage', backref='vehicle', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('VehicleDocument', backref='vehicle', lazy=True, cascade='all, delete-orphan')
    cost_sheet = db.relationship('CostSheet', backref='vehicle', lazy=True, uselist=False, cascade='all, delete-orphan')
    quotations = db.relationship('Quotation', backref='vehicle', lazy=True)
    sales = db.relationship('Sale', backref='vehicle', lazy=True)
    make_ref = db.relationship('VehicleMake', foreign_keys=[make_id])
    model_ref = db.relationship('VehicleModel', foreign_keys=[model_id])

    def primary_image(self):
        p = VehicleImage.query.filter_by(vehicle_id=self.id, is_primary=True).first()
        if p:
            return p.filename
        img = VehicleImage.query.filter_by(vehicle_id=self.id).first()
        return img.filename if img else None

    def display_price(self):
        if self.selling_price:
            return f"LKR {self.selling_price:,.0f}"
        return "Price on Request"

    @property
    def status_badge(self):
        badges = {
            'available': 'success',
            'reserved': 'warning',
            'sold': 'secondary',
            'under_inspection': 'info',
        }
        return badges.get(self.status, 'secondary')

class VehicleImage(db.Model):
    __tablename__ = 'vehicle_images'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class VehicleDocument(db.Model):
    __tablename__ = 'vehicle_documents'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    doc_type = db.Column(db.String(50))
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Cost Sheet ───────────────────────────────────────────────────────────────
class CostSheet(db.Model):
    __tablename__ = 'cost_sheets'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False, unique=True)
    currency = db.Column(db.String(10), default='USD')
    exchange_rate = db.Column(db.Float, default=320.0)
    purchase_price_fc = db.Column(db.Float, default=0)
    lc_value = db.Column(db.Float, default=0)
    bank_charges = db.Column(db.Float, default=0)
    lc_interest = db.Column(db.Float, default=0)
    lc_date = db.Column(db.Date)
    import_duty = db.Column(db.Float, default=0)
    customs_levy = db.Column(db.Float, default=0)
    excise_duty = db.Column(db.Float, default=0)
    vat_import = db.Column(db.Float, default=0)
    port_handling = db.Column(db.Float, default=0)
    freight = db.Column(db.Float, default=0)
    insurance_import = db.Column(db.Float, default=0)
    agent_fees = db.Column(db.Float, default=0)
    clearing_charges = db.Column(db.Float, default=0)
    inland_transport = db.Column(db.Float, default=0)
    logistics_tax = db.Column(db.Float, default=0)
    other_costs = db.Column(db.Float, default=0)
    other_costs_note = db.Column(db.String(200))
    total_landed_cost = db.Column(db.Float, default=0)
    target_margin_pct = db.Column(db.Float, default=15.0)
    target_selling_price = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calc_total(self):
        purchase_lkr = (self.purchase_price_fc or 0) * (self.exchange_rate or 1)
        total = sum([
            purchase_lkr,
            self.bank_charges or 0, self.lc_interest or 0,
            self.import_duty or 0, self.customs_levy or 0,
            self.excise_duty or 0, self.vat_import or 0,
            self.port_handling or 0, self.freight or 0,
            self.insurance_import or 0, self.agent_fees or 0,
            self.clearing_charges or 0, self.inland_transport or 0,
            self.logistics_tax or 0,
            self.other_costs or 0,
        ])
        return total

    def calc_target_price(self):
        total = self.calc_total()
        margin = self.target_margin_pct or 15
        if margin >= 100:
            return 0
        return total / (1 - margin / 100)

# ─── Customer ─────────────────────────────────────────────────────────────────
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nic_passport = db.Column(db.String(30))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    notes = db.Column(db.Text)
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    quotations = db.relationship('Quotation', backref='customer', lazy=True)
    sales = db.relationship('Sale', backref='customer', lazy=True)

# ─── Quotation ────────────────────────────────────────────────────────────────
class Quotation(db.Model):
    __tablename__ = 'quotations'
    id = db.Column(db.Integer, primary_key=True)
    quote_no = db.Column(db.String(30), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'))
    doc_type = db.Column(db.String(20), default='quotation')  # quotation, proforma_invoice, tax_invoice
    status = db.Column(db.String(20), default='draft')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    valid_until = db.Column(db.Date)
    payment_terms = db.Column(db.Text)
    discount_amount = db.Column(db.Float, default=0)
    discount_pct = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    subtotal = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='LKR')
    notes = db.Column(db.Text)
    version = db.Column(db.Integer, default=1)
    parent_id = db.Column(db.Integer, db.ForeignKey('quotations.id'))

    items = db.relationship('QuotationItem', backref='quotation', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])
    revisions = db.relationship('Quotation', backref=db.backref('parent', remote_side=[id]))

    def calculate_totals(self):
        subtotal = sum(item.quantity * item.unit_price for item in self.items)
        discount = self.discount_amount or (subtotal * (self.discount_pct or 0) / 100)
        taxable = subtotal - discount
        tax = taxable * (self.tax_rate or 0) / 100
        self.subtotal = subtotal
        self.tax_amount = tax
        self.total = taxable + tax
        return self.total

    @property
    def status_badge(self):
        badges = {
            'draft': 'secondary', 'sent': 'info', 'accepted': 'success',
            'invoiced': 'primary', 'paid': 'success', 'cancelled': 'danger',
        }
        return badges.get(self.status, 'secondary')

    @property
    def doc_type_label(self):
        labels = {
            'quotation': 'Quotation', 'proforma_invoice': 'Proforma Invoice',
            'tax_invoice': 'Tax Invoice',
        }
        return labels.get(self.doc_type, self.doc_type.title())

class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

# ─── Sale ─────────────────────────────────────────────────────────────────────
class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    sale_ref = db.Column(db.String(30), unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'))
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(30), default='lead')
    sale_price = db.Column(db.Float)
    deposit_amount = db.Column(db.Float, default=0)
    has_leasing = db.Column(db.Boolean, default=False)
    leasing_bank = db.Column(db.String(100))
    loan_amount = db.Column(db.Float)
    leasing_approval_status = db.Column(db.String(30))
    has_trade_in = db.Column(db.Boolean, default=False)
    trade_in_vehicle = db.Column(db.String(200))
    trade_in_value = db.Column(db.Float)
    delivery_date = db.Column(db.Date)
    delivery_notes = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship('Payment', backref='sale', lazy=True, cascade='all, delete-orphan')
    salesperson = db.relationship('User', foreign_keys=[salesperson_id])

    def total_paid(self):
        return sum(p.amount for p in self.payments)

    def balance_due(self):
        return (self.sale_price or 0) - self.total_paid()

    @property
    def status_badge(self):
        badges = {
            'lead': 'secondary', 'negotiation': 'info', 'deposit_paid': 'warning',
            'full_payment': 'primary', 'delivered': 'success', 'cancelled': 'danger',
        }
        return badges.get(self.status, 'secondary')

    @property
    def status_label(self):
        labels = {
            'lead': 'Lead', 'negotiation': 'Negotiation', 'deposit_paid': 'Deposit Paid',
            'full_payment': 'Full Payment', 'delivered': 'Delivered', 'cancelled': 'Cancelled',
        }
        return labels.get(self.status, self.status.title())

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30))
    payment_date = db.Column(db.Date, nullable=False)
    reference_no = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))


# ─── Expense ──────────────────────────────────────────────────────────────────
class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Inquiry ──────────────────────────────────────────────────────────────────
class Inquiry(db.Model):
    __tablename__ = 'inquiries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle_ref = db.relationship('Vehicle', foreign_keys=[vehicle_id])

# ─── Audit Log ────────────────────────────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))
    module = db.Column(db.String(50))
    record_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])

# ─── System Settings ──────────────────────────────────────────────────────────
class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), default='Sonnac Lanka Enterprises')
    company_tagline = db.Column(db.String(200), default='Your Trusted Vehicle Partner')
    company_address = db.Column(db.Text, default='Negombo, Sri Lanka')
    company_phone = db.Column(db.String(20), default='+94 XX XXX XXXX')
    company_email = db.Column(db.String(120), default='info@sonnac.lk')
    company_logo = db.Column(db.String(255))
    tax_rate = db.Column(db.Float, default=0)
    default_currency = db.Column(db.String(10), default='LKR')
    quote_prefix = db.Column(db.String(20), default='SLE-QT')
    invoice_prefix = db.Column(db.String(20), default='SLE-INV')
    pi_prefix = db.Column(db.String(20), default='SLE-PI')
    bank_details = db.Column(db.Text)
    terms_conditions = db.Column(db.Text)
    google_maps_embed = db.Column(db.Text)
    whatsapp_number = db.Column(db.String(20))
    facebook_url = db.Column(db.String(200))
    instagram_url = db.Column(db.String(200))
    youtube_url = db.Column(db.String(200))

    # Convenience aliases for templates
    @property
    def address(self): return self.company_address
    @property
    def phone(self): return self.company_phone
    @property
    def email(self): return self.company_email
    @property
    def logo(self): return self.company_logo
    @property
    def currency(self): return self.default_currency
    @property
    def terms_and_conditions(self): return self.terms_conditions

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
