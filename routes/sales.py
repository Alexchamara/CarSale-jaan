from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Sale, Payment, Vehicle, Customer, Quotation, User
from utils import log_action, generate_sale_ref
from datetime import date

sales_bp = Blueprint('sales', __name__)

PIPELINE_STAGES = [
    ('lead', 'Lead'), ('negotiation', 'Negotiation'),
    ('deposit_paid', 'Deposit Paid'), ('full_payment', 'Full Payment'),
    ('delivered', 'Delivered'), ('cancelled', 'Cancelled'),
]
PAYMENT_METHODS = ['Cash', 'Bank Transfer', 'Cheque', 'Leasing', 'Card']


@sales_bp.route('/')
@login_required
def pipeline():
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    query = Sale.query
    if status_filter:
        query = query.filter(Sale.status == status_filter)
    if search:
        query = query.join(Customer).filter(
            Customer.name.ilike(f'%{search}%') |
            Sale.sale_ref.ilike(f'%{search}%')
        )
    query = query.order_by(Sale.created_at.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # Stage counts and pipeline dict (stage -> list of sales)
    stage_counts = {s[0]: Sale.query.filter_by(status=s[0]).count() for s in PIPELINE_STAGES}
    pipeline = {}
    for stage, _label in PIPELINE_STAGES:
        q = Sale.query.filter_by(status=stage)
        if search:
            q = q.join(Customer).filter(
                Customer.name.ilike(f'%{search}%') |
                Sale.sale_ref.ilike(f'%{search}%')
            )
        pipeline[stage] = q.order_by(Sale.created_at.desc()).all()

    return render_template('admin/sales/pipeline.html', sales=pagination.items,
                           all_sales=pagination.items,
                           pagination=pagination, pipeline_stages=PIPELINE_STAGES,
                           stage_counts=stage_counts, pipeline=pipeline,
                           filters=dict(q=search, status=status_filter))


@sales_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if not current_user.has_permission('sales', 'create'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('sales.pipeline'))

    customers = Customer.query.order_by(Customer.name).all()
    vehicles = Vehicle.query.filter_by(is_archived=False, status='available').order_by(Vehicle.make).all()
    salespeople = User.query.filter_by(is_active=True).filter(
        User.role.in_(['admin', 'sales_manager', 'sales_executive'])).all()
    quotations = Quotation.query.filter_by(status='accepted').order_by(Quotation.created_at.desc()).all()

    if request.method == 'POST':
        sale = Sale(
            sale_ref=generate_sale_ref(),
            vehicle_id=int(request.form.get('vehicle_id')),
            customer_id=int(request.form.get('customer_id')),
            quotation_id=int(request.form.get('quotation_id')) if request.form.get('quotation_id') else None,
            salesperson_id=int(request.form.get('salesperson_id')) if request.form.get('salesperson_id') else None,
            status=request.form.get('status', 'lead'),
            sale_price=float(request.form.get('sale_price') or 0) or None,
            deposit_amount=float(request.form.get('deposit_amount') or 0),
            has_leasing=bool(request.form.get('has_leasing')),
            leasing_bank=request.form.get('leasing_bank'),
            loan_amount=float(request.form.get('loan_amount') or 0) or None,
            leasing_approval_status=request.form.get('leasing_approval_status'),
            has_trade_in=bool(request.form.get('has_trade_in')),
            trade_in_vehicle=request.form.get('trade_in_vehicle'),
            trade_in_value=float(request.form.get('trade_in_value') or 0) or None,
            notes=request.form.get('notes'),
        )
        delivery_str = request.form.get('delivery_date')
        if delivery_str:
            sale.delivery_date = date.fromisoformat(delivery_str)
        follow_up_str = request.form.get('follow_up_date')
        if follow_up_str:
            sale.follow_up_date = date.fromisoformat(follow_up_str)

        db.session.add(sale)
        # Update vehicle status based on initial sale stage
        vehicle = Vehicle.query.get(sale.vehicle_id)
        if vehicle:
            if sale.status == 'delivered':
                vehicle.status = 'sold'
            elif sale.status in ['deposit_paid', 'full_payment']:
                vehicle.status = 'reserved'
            # lead / negotiation → leave as available
        db.session.commit()
        log_action(current_user.id, 'create', 'sales', sale.id, f'Created sale {sale.sale_ref}')
        flash(f'Sale {sale.sale_ref} created.', 'success')
        return redirect(url_for('sales.view_sale', sale_id=sale.id))

    return render_template('admin/sales/form.html', sale=None,
                           customers=customers, vehicles=vehicles,
                           salespeople=salespeople, quotations=quotations,
                           pipeline_stages=PIPELINE_STAGES, payment_methods=PAYMENT_METHODS)


@sales_bp.route('/<int:sale_id>')
@login_required
def view_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('admin/sales/view.html', sale=sale,
                           pipeline_stages=PIPELINE_STAGES, payment_methods=PAYMENT_METHODS)


@sales_bp.route('/<int:sale_id>/status', methods=['POST'])
@login_required
def update_status(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    if not current_user.has_permission('sales', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('sales.view_sale', sale_id=sale_id))
    new_status = request.form.get('status')
    valid = [s[0] for s in PIPELINE_STAGES]
    if new_status in valid:
        sale.status = new_status
        vehicle = sale.vehicle
        if vehicle:
            if new_status == 'delivered':
                vehicle.status = 'sold'
            elif new_status in ['deposit_paid', 'full_payment']:
                vehicle.status = 'reserved'
            elif new_status == 'cancelled':
                vehicle.status = 'available'
        db.session.commit()
        log_action(current_user.id, 'status_change', 'sales', sale.id,
                   f'Stage changed to {new_status}')
        flash(f'Stage updated to {new_status.replace("_"," ").title()}.', 'success')
    return redirect(url_for('sales.view_sale', sale_id=sale_id))


@sales_bp.route('/<int:sale_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    if not current_user.has_permission('sales', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('sales.view_sale', sale_id=sale_id))

    customers = Customer.query.order_by(Customer.name).all()
    vehicles = Vehicle.query.filter_by(is_archived=False).order_by(Vehicle.make).all()
    salespeople = User.query.filter_by(is_active=True).all()
    quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()

    if request.method == 'POST':
        old_status = sale.status
        old_vehicle_id = sale.vehicle_id
        sale.customer_id = int(request.form.get('customer_id'))
        sale.vehicle_id = int(request.form.get('vehicle_id'))
        sale.quotation_id = int(request.form.get('quotation_id')) if request.form.get('quotation_id') else None
        sale.salesperson_id = int(request.form.get('salesperson_id')) if request.form.get('salesperson_id') else None
        sale.status = request.form.get('status', 'lead')
        sale.sale_price = float(request.form.get('sale_price') or 0) or None
        sale.deposit_amount = float(request.form.get('deposit_amount') or 0)
        sale.has_leasing = bool(request.form.get('has_leasing'))
        sale.leasing_bank = request.form.get('leasing_bank')
        sale.loan_amount = float(request.form.get('loan_amount') or 0) or None
        sale.leasing_approval_status = request.form.get('leasing_approval_status')
        sale.has_trade_in = bool(request.form.get('has_trade_in'))
        sale.trade_in_vehicle = request.form.get('trade_in_vehicle')
        sale.trade_in_value = float(request.form.get('trade_in_value') or 0) or None
        sale.notes = request.form.get('notes')
        delivery_str = request.form.get('delivery_date')
        sale.delivery_date = date.fromisoformat(delivery_str) if delivery_str else None
        follow_up_str = request.form.get('follow_up_date')
        sale.follow_up_date = date.fromisoformat(follow_up_str) if follow_up_str else None

        # If vehicle changed, reset old vehicle back to available
        if old_vehicle_id != sale.vehicle_id:
            old_vehicle = Vehicle.query.get(old_vehicle_id)
            if old_vehicle:
                old_vehicle.status = 'available'

        # Update new vehicle status
        vehicle = Vehicle.query.get(sale.vehicle_id)
        if vehicle:
            if sale.status == 'delivered':
                vehicle.status = 'sold'
            elif sale.status in ['deposit_paid', 'full_payment']:
                vehicle.status = 'reserved'
            elif sale.status == 'cancelled':
                vehicle.status = 'available'
            elif sale.status in ['lead', 'negotiation'] and old_status not in ['deposit_paid', 'full_payment', 'delivered']:
                vehicle.status = 'available'

        db.session.commit()
        log_action(current_user.id, 'update', 'sales', sale.id, f'Updated sale {sale.sale_ref}')
        flash('Sale updated.', 'success')
        return redirect(url_for('sales.view_sale', sale_id=sale_id))

    return render_template('admin/sales/form.html', sale=sale,
                           customers=customers, vehicles=vehicles,
                           salespeople=salespeople, quotations=quotations,
                           pipeline_stages=PIPELINE_STAGES, payment_methods=PAYMENT_METHODS)


@sales_bp.route('/<int:sale_id>/payment', methods=['POST'])
@login_required
def add_payment(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    amount_str = request.form.get('amount', '0')
    amount = float(amount_str or 0)
    method = request.form.get('payment_method', 'Cash')
    payment_date_str = request.form.get('payment_date') or date.today().isoformat()
    reference = request.form.get('reference_no', '')
    notes = request.form.get('notes', '')

    payment = Payment(
        sale_id=sale_id, amount=amount, payment_method=method,
        payment_date=date.fromisoformat(payment_date_str),
        reference_no=reference, notes=notes, created_by=current_user.id,
    )
    db.session.add(payment)

    # Auto-advance status
    total_paid = sale.total_paid() + amount
    if sale.sale_price and total_paid >= sale.sale_price:
        sale.status = 'full_payment'
    elif amount > 0 and sale.status == 'lead':
        sale.status = 'deposit_paid'

    db.session.commit()
    log_action(current_user.id, 'payment', 'sales', sale_id,
               f'Payment of LKR {amount:,.0f} via {method}')
    flash(f'Payment of LKR {amount:,.0f} recorded.', 'success')
    return redirect(url_for('sales.view_sale', sale_id=sale_id))
