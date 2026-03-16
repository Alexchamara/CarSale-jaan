import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, SystemSettings, AuditLog
from utils import save_upload, allowed_image, log_action

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.has_permission('settings', 'view'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin_home'))
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST' and current_user.has_permission('settings', 'edit'):
        settings.company_name = request.form.get('company_name', '').strip()
        settings.company_tagline = request.form.get('company_tagline', '').strip()
        settings.company_address = request.form.get('company_address', '')
        settings.company_phone = request.form.get('company_phone', '').strip()
        settings.company_email = request.form.get('company_email', '').strip()
        settings.tax_rate = float(request.form.get('tax_rate') or 0)
        settings.default_currency = request.form.get('default_currency', 'LKR')
        settings.quote_prefix = request.form.get('quote_prefix', 'SLE-QT').strip()
        settings.invoice_prefix = request.form.get('invoice_prefix', 'SLE-INV').strip()
        settings.pi_prefix = request.form.get('pi_prefix', 'SLE-PI').strip()
        settings.bank_details = request.form.get('bank_details', '')
        settings.terms_conditions = request.form.get('terms_conditions', '')
        settings.google_maps_embed = request.form.get('google_maps_embed', '')
        settings.whatsapp_number = request.form.get('whatsapp_number', '').strip()
        settings.facebook_url = request.form.get('facebook_url', '').strip()
        settings.instagram_url = request.form.get('instagram_url', '').strip()

        logo_file = request.files.get('company_logo')
        if logo_file and logo_file.filename and allowed_image(logo_file.filename):
            fname = save_upload(logo_file, 'logos')
            settings.company_logo = fname

        db.session.commit()
        log_action(current_user.id, 'update', 'settings', 1, 'Updated system settings')
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('settings.index'))

    return render_template('admin/settings/index.html', settings=settings)


@settings_bp.route('/audit-log')
@login_required
def audit_log():
    if not current_user.has_permission('settings', 'view'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin_home'))
    page = request.args.get('page', 1, type=int)
    module_filter = request.args.get('module', '')
    query = AuditLog.query
    if module_filter:
        query = query.filter(AuditLog.module == module_filter)
    query = query.order_by(AuditLog.timestamp.desc())
    pagination = query.paginate(page=page, per_page=30, error_out=False)
    modules = [m[0] for m in db.session.query(AuditLog.module).distinct().all() if m[0]]
    return render_template('admin/audit_log.html', logs=pagination.items,
                           pagination=pagination, modules=modules,
                           filters=dict(module=module_filter))
