from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, VehicleMake, VehicleModel, Vehicle
from utils import log_action

vehicle_meta_bp = Blueprint('vehicle_meta', __name__)


def require_inv_perm(action='view'):
    if not current_user.has_permission('inventory', action):
        flash('You do not have permission for this action.', 'danger')
        return False
    return True


@vehicle_meta_bp.route('/makes', methods=['GET', 'POST'])
@login_required
def makes():
    if not require_inv_perm('view'):
        return redirect(url_for('admin_home'))
    if request.method == 'POST' and require_inv_perm('edit'):
        name = request.form.get('name', '').strip()
        if name:
            existing = VehicleMake.query.filter(db.func.lower(VehicleMake.name) == name.lower()).first()
            if existing:
                flash('Make already exists.', 'warning')
            else:
                mk = VehicleMake(name=name)
                db.session.add(mk)
                db.session.commit()
                log_action(current_user.id, 'create', 'inventory', mk.id, f'Created make {name}')
                flash('Make added.', 'success')
        return redirect(url_for('vehicle_meta.makes'))

    makes = VehicleMake.query.order_by(VehicleMake.is_active.desc(), VehicleMake.name).all()
    inactive_count = Vehicle.query.filter(Vehicle.make_id.isnot(None), VehicleMake.id == Vehicle.make_id, VehicleMake.is_active == False).count() if makes else 0
    return render_template('admin/meta/makes.html', makes=makes, inactive_count=inactive_count)


@vehicle_meta_bp.route('/makes/<int:make_id>/toggle', methods=['POST'])
@login_required
def toggle_make(make_id):
    if not require_inv_perm('edit'):
        return redirect(url_for('vehicle_meta.makes'))
    mk = VehicleMake.query.get_or_404(make_id)
    mk.is_active = not mk.is_active
    db.session.commit()
    action = 'activated' if mk.is_active else 'deactivated'
    log_action(current_user.id, 'update', 'inventory', mk.id, f'{action} make {mk.name}')
    flash(f'Make {action}.', 'success')
    return redirect(url_for('vehicle_meta.makes'))


@vehicle_meta_bp.route('/makes/<int:make_id>/delete', methods=['POST'])
@login_required
def delete_make(make_id):
    if not require_inv_perm('edit'):
        return redirect(url_for('vehicle_meta.makes'))
    mk = VehicleMake.query.get_or_404(make_id)
    in_use = Vehicle.query.filter_by(make_id=mk.id).count() > 0 or VehicleModel.query.filter_by(make_id=mk.id).count() > 0
    if in_use:
        flash('Make is in use; deactivate instead.', 'warning')
        return redirect(url_for('vehicle_meta.makes'))
    db.session.delete(mk)
    db.session.commit()
    log_action(current_user.id, 'delete', 'inventory', make_id, f'Deleted make {mk.name}')
    flash('Make deleted.', 'success')
    return redirect(url_for('vehicle_meta.makes'))


@vehicle_meta_bp.route('/models', methods=['GET', 'POST'])
@login_required
def models():
    if not require_inv_perm('view'):
        return redirect(url_for('admin_home'))
    makes = VehicleMake.query.order_by(VehicleMake.name).all()
    selected_make_id = request.args.get('make_id', type=int)
    models_query = VehicleModel.query
    if selected_make_id:
        models_query = models_query.filter(VehicleModel.make_id == selected_make_id)
    models_query = models_query.order_by(VehicleModel.is_active.desc(), VehicleModel.name)
    models_list = models_query.all()

    if request.method == 'POST' and require_inv_perm('edit'):
        make_id = request.form.get('make_id', type=int)
        name = request.form.get('name', '').strip()
        if not make_id:
            flash('Select a make for the model.', 'warning')
            return redirect(url_for('vehicle_meta.models', make_id=selected_make_id or ''))
        if name:
            existing = VehicleModel.query.filter(VehicleModel.make_id == make_id, db.func.lower(VehicleModel.name) == name.lower()).first()
            if existing:
                flash('Model already exists for this make.', 'warning')
            else:
                mdl = VehicleModel(make_id=make_id, name=name)
                db.session.add(mdl)
                db.session.commit()
                log_action(current_user.id, 'create', 'inventory', mdl.id, f'Created model {name}')
                flash('Model added.', 'success')
        return redirect(url_for('vehicle_meta.models', make_id=make_id))

    return render_template('admin/meta/models.html', models=models_list, makes=makes, selected_make_id=selected_make_id)


@vehicle_meta_bp.route('/models/<int:model_id>/toggle', methods=['POST'])
@login_required
def toggle_model(model_id):
    if not require_inv_perm('edit'):
        return redirect(url_for('vehicle_meta.models'))
    mdl = VehicleModel.query.get_or_404(model_id)
    mdl.is_active = not mdl.is_active
    db.session.commit()
    action = 'activated' if mdl.is_active else 'deactivated'
    log_action(current_user.id, 'update', 'inventory', mdl.id, f'{action} model {mdl.name}')
    flash(f'Model {action}.', 'success')
    return redirect(url_for('vehicle_meta.models', make_id=mdl.make_id))


@vehicle_meta_bp.route('/models/<int:model_id>/delete', methods=['POST'])
@login_required
def delete_model(model_id):
    if not require_inv_perm('edit'):
        return redirect(url_for('vehicle_meta.models'))
    mdl = VehicleModel.query.get_or_404(model_id)
    in_use = Vehicle.query.filter_by(model_id=mdl.id).count() > 0
    if in_use:
        flash('Model is in use; deactivate instead.', 'warning')
        return redirect(url_for('vehicle_meta.models', make_id=mdl.make_id))
    make_id = mdl.make_id
    db.session.delete(mdl)
    db.session.commit()
    log_action(current_user.id, 'delete', 'inventory', model_id, f'Deleted model {mdl.name}')
    flash('Model deleted.', 'success')
    return redirect(url_for('vehicle_meta.models', make_id=make_id))
