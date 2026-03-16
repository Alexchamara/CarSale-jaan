from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, Vehicle, CostSheet, SystemSettings
from utils import log_action, generate_cost_sheet_pdf
import io

costing_bp = Blueprint('costing', __name__)

CURRENCIES = ['USD', 'JPY', 'EUR', 'GBP', 'AUD', 'SGD', 'LKR']


@costing_bp.route('/')
@login_required
def list_costing():
    """List all non-archived, non-sold vehicles with costing status."""
    vehicles = (Vehicle.query
                .filter_by(is_archived=False)
                .filter(Vehicle.status != 'sold')
                .order_by(Vehicle.created_at.desc())
                .all())
    return render_template('admin/costing/list.html', vehicles=vehicles)


@costing_bp.route('/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def cost_sheet(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    cs = vehicle.cost_sheet or CostSheet(vehicle_id=vehicle_id)

    if request.method == 'POST':
        cs.currency = request.form.get('currency', 'USD')
        cs.exchange_rate = float(request.form.get('exchange_rate') or 1)
        cs.purchase_price_fc = float(request.form.get('purchase_price_fc') or 0)
        cs.lc_value = float(request.form.get('lc_value') or 0)
        cs.bank_charges = float(request.form.get('bank_charges') or 0)
        cs.lc_interest = float(request.form.get('lc_interest') or 0)
        lc_date_str = request.form.get('lc_date')
        if lc_date_str:
            from datetime import date
            cs.lc_date = date.fromisoformat(lc_date_str)
        cs.import_duty = float(request.form.get('import_duty') or 0)
        cs.customs_levy = float(request.form.get('customs_levy') or 0)
        cs.excise_duty = float(request.form.get('excise_duty') or 0)
        cs.vat_import = float(request.form.get('vat_import') or 0)
        cs.port_handling = float(request.form.get('port_handling') or 0)
        cs.freight = float(request.form.get('freight') or 0)
        cs.insurance_import = float(request.form.get('insurance_import') or 0)
        cs.agent_fees = float(request.form.get('agent_fees') or 0)
        cs.clearing_charges = float(request.form.get('clearing_charges') or 0)
        cs.inland_transport = float(request.form.get('inland_transport') or 0)
        cs.other_costs = float(request.form.get('other_costs') or 0)
        cs.other_costs_note = request.form.get('other_costs_note')
        cs.target_margin_pct = float(request.form.get('target_margin_pct') or 15)
        cs.notes = request.form.get('notes')

        cs.total_landed_cost = cs.calc_total()
        cs.target_selling_price = cs.calc_target_price()

        if not cs.id:
            db.session.add(cs)
        db.session.commit()

        # Auto update vehicle selling price suggestion
        if request.form.get('apply_price'):
            vehicle.selling_price = cs.target_selling_price
            db.session.commit()

        log_action(current_user.id, 'update', 'costing', vehicle_id, 'Updated cost sheet')
        flash('Cost sheet saved successfully.', 'success')
        return redirect(url_for('costing.cost_sheet', vehicle_id=vehicle_id))

    return render_template('admin/costing/form.html', vehicle=vehicle, cs=cs,
                           cost_sheet=cs, currencies=CURRENCIES)


@costing_bp.route('/<int:vehicle_id>/pdf')
@login_required
def cost_sheet_pdf(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    cs = vehicle.cost_sheet
    if not cs:
        flash('No cost sheet found for this vehicle.', 'warning')
        return redirect(url_for('costing.cost_sheet', vehicle_id=vehicle_id))
    pdf_bytes = generate_cost_sheet_pdf(vehicle, cs)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'cost_sheet_{vehicle.make}_{vehicle.model}_{vehicle.id}.pdf'
    )
