from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from models import db, Quotation, QuotationItem, Customer, Vehicle, SystemSettings
from utils import log_action, generate_quotation_pdf, generate_quote_number
from datetime import date, datetime, timedelta
import io

quotations_bp = Blueprint('quotations', __name__)

DOC_TYPES = ['quotation', 'proforma_invoice', 'tax_invoice']
STATUSES = ['draft', 'sent', 'accepted', 'invoiced', 'paid', 'cancelled']
CURRENCIES = ['LKR', 'USD', 'EUR', 'GBP']


@quotations_bp.route('/')
@login_required
def list_quotations():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    doc_type_filter = request.args.get('doc_type', '')
    search = request.args.get('q', '')

    query = Quotation.query
    if status_filter:
        query = query.filter(Quotation.status == status_filter)
    if doc_type_filter:
        query = query.filter(Quotation.doc_type == doc_type_filter)
    if search:
        query = query.join(Customer).filter(
            Quotation.quote_no.ilike(f'%{search}%') |
            Customer.name.ilike(f'%{search}%')
        )
    query = query.order_by(Quotation.created_at.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template('admin/quotations/list.html', quotations=pagination.items,
                           pagination=pagination, statuses=STATUSES, doc_types=DOC_TYPES,
                           filters=dict(q=search, status=status_filter, doc_type=doc_type_filter))


@quotations_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_quotation():
    if not current_user.has_permission('quotations', 'create'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('quotations.list_quotations'))

    customers = Customer.query.order_by(Customer.name).all()
    vehicles = Vehicle.query.filter_by(is_archived=False).filter(
        Vehicle.status.in_(['available', 'reserved'])).order_by(Vehicle.make).all()
    settings = SystemSettings.query.first()

    if request.method == 'POST':
        doc_type = request.form.get('doc_type', 'quotation')
        q = Quotation(
            quote_no=generate_quote_number(doc_type, settings),
            customer_id=int(request.form.get('customer_id')),
            vehicle_id=int(request.form.get('vehicle_id')) if request.form.get('vehicle_id') else None,
            doc_type=doc_type,
            status='draft',
            currency=request.form.get('currency', 'LKR'),
            payment_terms=request.form.get('payment_terms'),
            notes=request.form.get('notes'),
            discount_pct=float(request.form.get('discount_pct') or 0),
            discount_amount=float(request.form.get('discount_amount') or 0),
            tax_rate=float(request.form.get('tax_rate') or (settings.tax_rate if settings else 0)),
            created_by=current_user.id,
        )
        validity_str = request.form.get('valid_until')
        if validity_str:
            q.valid_until = date.fromisoformat(validity_str)
        else:
            q.valid_until = date.today() + timedelta(days=30)

        db.session.add(q)
        db.session.flush()

        # Items
        descs = request.form.getlist('item_desc[]')
        qtys = request.form.getlist('item_qty[]')
        prices = request.form.getlist('item_price[]')
        for desc, qty, price in zip(descs, qtys, prices):
            if desc.strip():
                item_qty = float(qty or 1)
                item_price = float(price or 0)
                item = QuotationItem(quotation_id=q.id, description=desc.strip(),
                                     quantity=item_qty, unit_price=item_price,
                                     total=item_qty * item_price)
                db.session.add(item)

        db.session.flush()
        q.calculate_totals()
        db.session.commit()
        log_action(current_user.id, 'create', 'quotations', q.id, f'Created {q.doc_type_label} {q.quote_no}')
        flash(f'{q.doc_type_label} {q.quote_no} created successfully.', 'success')
        return redirect(url_for('quotations.view_quotation', quote_id=q.id))

    return render_template('admin/quotations/form.html', quotation=None,
                           customers=customers, vehicles=vehicles,
                           doc_types=DOC_TYPES, currencies=CURRENCIES,
                           settings=settings,
                           default_validity=(date.today() + timedelta(days=30)).isoformat())


@quotations_bp.route('/<int:quote_id>')
@login_required
def view_quotation(quote_id):
    quotation = Quotation.query.get_or_404(quote_id)
    return render_template('admin/quotations/view.html', quotation=quotation)


@quotations_bp.route('/<int:quote_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_quotation(quote_id):
    quotation = Quotation.query.get_or_404(quote_id)
    if not current_user.has_permission('quotations', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('quotations.view_quotation', quote_id=quote_id))

    customers = Customer.query.order_by(Customer.name).all()
    vehicles = Vehicle.query.filter_by(is_archived=False).order_by(Vehicle.make).all()
    settings = SystemSettings.query.first()

    if request.method == 'POST':
        quotation.customer_id = int(request.form.get('customer_id'))
        quotation.vehicle_id = int(request.form.get('vehicle_id')) if request.form.get('vehicle_id') else None
        quotation.currency = request.form.get('currency', 'LKR')
        quotation.payment_terms = request.form.get('payment_terms')
        quotation.notes = request.form.get('notes')
        quotation.discount_pct = float(request.form.get('discount_pct') or 0)
        quotation.discount_amount = float(request.form.get('discount_amount') or 0)
        quotation.tax_rate = float(request.form.get('tax_rate') or 0)
        validity_str = request.form.get('valid_until')
        if validity_str:
            quotation.valid_until = date.fromisoformat(validity_str)

        # Rebuild items
        for item in quotation.items:
            db.session.delete(item)
        db.session.flush()

        descs = request.form.getlist('item_desc[]')
        qtys = request.form.getlist('item_qty[]')
        prices = request.form.getlist('item_price[]')
        for desc, qty, price in zip(descs, qtys, prices):
            if desc.strip():
                item_qty = float(qty or 1)
                item_price = float(price or 0)
                item = QuotationItem(quotation_id=quotation.id, description=desc.strip(),
                                     quantity=item_qty, unit_price=item_price,
                                     total=item_qty * item_price)
                db.session.add(item)

        db.session.flush()
        quotation.calculate_totals()
        db.session.commit()
        log_action(current_user.id, 'update', 'quotations', quotation.id, f'Updated {quotation.quote_no}')
        flash('Document updated successfully.', 'success')
        return redirect(url_for('quotations.view_quotation', quote_id=quote_id))

    return render_template('admin/quotations/form.html', quotation=quotation,
                           customers=customers, vehicles=vehicles,
                           doc_types=DOC_TYPES, currencies=CURRENCIES, settings=settings)


@quotations_bp.route('/<int:quote_id>/status/<status>', methods=['POST'])
@login_required
def update_status(quote_id, status):
    quotation = Quotation.query.get_or_404(quote_id)
    valid_statuses = ['draft', 'sent', 'accepted', 'invoiced', 'paid', 'cancelled']
    if status in valid_statuses:
        quotation.status = status
        db.session.commit()
        log_action(current_user.id, 'status_change', 'quotations', quote_id,
                   f'Status changed to {status}')
        flash(f'Status updated to {status.title()}.', 'success')
    return redirect(url_for('quotations.view_quotation', quote_id=quote_id))


@quotations_bp.route('/<int:quote_id>/convert/<doc_type>', methods=['POST'])
@login_required
def convert_document(quote_id, doc_type):
    source = Quotation.query.get_or_404(quote_id)
    if not current_user.has_permission('quotations', 'create'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('quotations.view_quotation', quote_id=quote_id))
    settings = SystemSettings.query.first()
    new_q = Quotation(
        quote_no=generate_quote_number(doc_type, settings),
        customer_id=source.customer_id,
        vehicle_id=source.vehicle_id,
        doc_type=doc_type,
        status='draft',
        currency=source.currency,
        payment_terms=source.payment_terms,
        notes=source.notes,
        discount_pct=source.discount_pct,
        discount_amount=source.discount_amount,
        tax_rate=source.tax_rate,
        valid_until=source.valid_until,
        created_by=current_user.id,
        parent_id=source.id,
        version=source.version + 1,
    )
    db.session.add(new_q)
    db.session.flush()
    for item in source.items:
        new_item = QuotationItem(quotation_id=new_q.id, description=item.description,
                                  quantity=item.quantity, unit_price=item.unit_price,
                                  total=item.total)
        db.session.add(new_item)
    db.session.flush()
    new_q.calculate_totals()
    db.session.commit()
    log_action(current_user.id, 'convert', 'quotations', new_q.id, f'Converted from {source.quote_no}')
    flash(f'Created {new_q.doc_type_label} {new_q.quote_no} from {source.quote_no}.', 'success')
    return redirect(url_for('quotations.view_quotation', quote_id=new_q.id))


@quotations_bp.route('/<int:quote_id>/pdf')
@login_required
def download_pdf(quote_id):
    quotation = Quotation.query.get_or_404(quote_id)
    pdf_bytes = generate_quotation_pdf(quotation)
    return send_file(
        io.BytesIO(pdf_bytes), mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{quotation.quote_no}.pdf'
    )


@quotations_bp.route('/<int:quote_id>/delete', methods=['POST'])
@login_required
def delete_quotation(quote_id):
    if not current_user.has_permission('quotations', 'delete'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('quotations.list_quotations'))
    quotation = Quotation.query.get_or_404(quote_id)
    db.session.delete(quotation)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('quotations.list_quotations'))
