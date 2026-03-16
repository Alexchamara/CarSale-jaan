from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Customer
from utils import log_action

customers_bp = Blueprint('customers', __name__)

SOURCES = ['Walk-in', 'Website', 'Referral', 'Social Media', 'Phone Inquiry', 'WhatsApp', 'Other']


@customers_bp.route('/')
@login_required
def list_customers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    query = Customer.query
    if search:
        query = query.filter(
            Customer.name.ilike(f'%{search}%') |
            Customer.email.ilike(f'%{search}%') |
            Customer.phone.ilike(f'%{search}%') |
            Customer.nic_passport.ilike(f'%{search}%')
        )
    query = query.order_by(Customer.name)
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/customers/list.html', customers=pagination.items,
                           pagination=pagination, filters=dict(q=search))


@customers_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_customer():
    if not current_user.has_permission('customers', 'create'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('customers.list_customers'))
    if request.method == 'POST':
        c = Customer(
            name=request.form.get('name', '').strip(),
            nic_passport=request.form.get('nic_passport', '').strip() or None,
            email=request.form.get('email', '').strip() or None,
            phone=request.form.get('phone', '').strip() or None,
            address=request.form.get('address'),
            city=request.form.get('city'),
            notes=request.form.get('notes'),
            source=request.form.get('source'),
        )
        db.session.add(c)
        db.session.commit()
        log_action(current_user.id, 'create', 'customers', c.id, f'Created customer {c.name}')
        flash(f'Customer {c.name} added.', 'success')
        return redirect(url_for('customers.view_customer', customer_id=c.id))
    return render_template('admin/customers/form.html', customer=None, sources=SOURCES)


@customers_bp.route('/<int:customer_id>')
@login_required
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template('admin/customers/form.html', customer=customer, sources=SOURCES, view_mode=True)


@customers_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if not current_user.has_permission('customers', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('customers.list_customers'))
    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip()
        customer.nic_passport = request.form.get('nic_passport', '').strip() or None
        customer.email = request.form.get('email', '').strip() or None
        customer.phone = request.form.get('phone', '').strip() or None
        customer.address = request.form.get('address')
        customer.city = request.form.get('city')
        customer.notes = request.form.get('notes')
        customer.source = request.form.get('source')
        db.session.commit()
        log_action(current_user.id, 'update', 'customers', customer.id, f'Updated customer {customer.name}')
        flash('Customer updated.', 'success')
        return redirect(url_for('customers.list_customers'))
    return render_template('admin/customers/form.html', customer=customer, sources=SOURCES)
