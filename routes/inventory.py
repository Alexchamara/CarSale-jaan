import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Vehicle, VehicleImage, VehicleDocument, SystemSettings
from utils import allowed_image, allowed_doc, save_upload, log_action
import io

inventory_bp = Blueprint('inventory', __name__)

BODY_TYPES = ['Sedan', 'SUV', 'Hatchback', 'Van', 'Pickup', 'Coupe', 'Wagon', 'Minivan', 'Bus', 'Truck', 'Other']
FUEL_TYPES = ['Petrol', 'Diesel', 'Hybrid', 'Electric', 'LPG', 'CNG']
TRANSMISSIONS = ['Automatic', 'Manual', 'CVT', 'Semi-Automatic']
CONDITIONS = ['A+', 'A', 'B+', 'B', 'C', 'D']
STATUSES = ['available', 'reserved', 'sold', 'under_inspection']


def require_perm(action):
    if not current_user.has_permission('inventory', action):
        flash('You do not have permission for this action.', 'danger')
        return False
    return True


@inventory_bp.route('/')
@login_required
def list_vehicles():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    make_filter = request.args.get('make', '')
    archived = request.args.get('archived', '0') == '1'

    query = Vehicle.query.filter_by(is_archived=archived)
    if search:
        query = query.filter(
            Vehicle.make.ilike(f'%{search}%') |
            Vehicle.model.ilike(f'%{search}%') |
            Vehicle.chassis_no.ilike(f'%{search}%') |
            Vehicle.reg_no.ilike(f'%{search}%')
        )
    if status_filter:
        query = query.filter(Vehicle.status == status_filter)
    if make_filter:
        query = query.filter(Vehicle.make == make_filter)

    query = query.order_by(Vehicle.created_at.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    makes = [m[0] for m in db.session.query(Vehicle.make).distinct().order_by(Vehicle.make).all() if m[0]]

    return render_template('admin/inventory/list.html', vehicles=pagination.items,
                           pagination=pagination, makes=makes,
                           filters=dict(q=search, status=status_filter, make=make_filter, archived=archived),
                           statuses=STATUSES)


@inventory_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_vehicle():
    if not require_perm('create'):
        return redirect(url_for('inventory.list_vehicles'))
    if request.method == 'POST':
        v = Vehicle(
            chassis_no=request.form.get('chassis_no') or None,
            engine_no=request.form.get('engine_no') or None,
            reg_no=request.form.get('reg_no') or None,
            make=request.form.get('make', '').strip(),
            model=request.form.get('model', '').strip(),
            year=int(request.form.get('year', 2020)),
            body_type=request.form.get('body_type'),
            fuel_type=request.form.get('fuel_type'),
            transmission=request.form.get('transmission'),
            color=request.form.get('color'),
            mileage=int(request.form.get('mileage') or 0) or None,
            condition_grade=request.form.get('condition_grade'),
            status=request.form.get('status', 'available'),
            selling_price=float(request.form.get('selling_price') or 0) or None,
            description=request.form.get('description'),
            internal_notes=request.form.get('internal_notes'),
            is_featured=bool(request.form.get('is_featured')),
            created_by=current_user.id,
        )
        db.session.add(v)
        db.session.commit()

        # Handle image uploads
        images = request.files.getlist('images')
        for i, img in enumerate(images):
            if img and img.filename and allowed_image(img.filename):
                fname = save_upload(img, 'vehicles')
                vi = VehicleImage(vehicle_id=v.id, filename=fname,
                                  is_primary=(i == 0), display_order=i)
                db.session.add(vi)

        db.session.commit()
        log_action(current_user.id, 'create', 'inventory', v.id, f'Created vehicle {v.make} {v.model}')
        flash(f'Vehicle {v.year} {v.make} {v.model} added successfully.', 'success')
        return redirect(url_for('inventory.view_vehicle', vehicle_id=v.id))

    return render_template('admin/inventory/form.html', vehicle=None,
                           body_types=BODY_TYPES, fuel_types=FUEL_TYPES,
                           transmissions=TRANSMISSIONS, conditions=CONDITIONS, statuses=STATUSES)


@inventory_bp.route('/<int:vehicle_id>')
@login_required
def view_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    return render_template('admin/inventory/view.html', vehicle=vehicle)


@inventory_bp.route('/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if not require_perm('edit'):
        return redirect(url_for('inventory.view_vehicle', vehicle_id=vehicle_id))
    if request.method == 'POST':
        vehicle.chassis_no = request.form.get('chassis_no') or None
        vehicle.engine_no = request.form.get('engine_no') or None
        vehicle.reg_no = request.form.get('reg_no') or None
        vehicle.make = request.form.get('make', '').strip()
        vehicle.model = request.form.get('model', '').strip()
        vehicle.year = int(request.form.get('year', vehicle.year))
        vehicle.body_type = request.form.get('body_type')
        vehicle.fuel_type = request.form.get('fuel_type')
        vehicle.transmission = request.form.get('transmission')
        vehicle.color = request.form.get('color')
        vehicle.mileage = int(request.form.get('mileage') or 0) or None
        vehicle.condition_grade = request.form.get('condition_grade')
        vehicle.status = request.form.get('status', 'available')
        vehicle.selling_price = float(request.form.get('selling_price') or 0) or None
        vehicle.description = request.form.get('description')
        vehicle.internal_notes = request.form.get('internal_notes')
        vehicle.is_featured = bool(request.form.get('is_featured'))
        db.session.commit()

        # New images
        images = request.files.getlist('images')
        existing_count = VehicleImage.query.filter_by(vehicle_id=vehicle_id).count()
        for i, img in enumerate(images):
            if img and img.filename and allowed_image(img.filename):
                fname = save_upload(img, 'vehicles')
                vi = VehicleImage(vehicle_id=vehicle.id, filename=fname,
                                  is_primary=(existing_count == 0 and i == 0),
                                  display_order=existing_count + i)
                db.session.add(vi)
        db.session.commit()
        log_action(current_user.id, 'update', 'inventory', vehicle.id, f'Updated vehicle {vehicle.make} {vehicle.model}')
        flash('Vehicle updated successfully.', 'success')
        return redirect(url_for('inventory.view_vehicle', vehicle_id=vehicle_id))

    return render_template('admin/inventory/form.html', vehicle=vehicle,
                           body_types=BODY_TYPES, fuel_types=FUEL_TYPES,
                           transmissions=TRANSMISSIONS, conditions=CONDITIONS, statuses=STATUSES)


@inventory_bp.route('/<int:vehicle_id>/archive', methods=['POST'])
@login_required
def archive_vehicle(vehicle_id):
    if not require_perm('delete'):
        return redirect(url_for('inventory.view_vehicle', vehicle_id=vehicle_id))
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    vehicle.is_archived = not vehicle.is_archived
    db.session.commit()
    action = 'archived' if vehicle.is_archived else 'restored'
    log_action(current_user.id, action, 'inventory', vehicle.id, f'{action.title()} vehicle')
    flash(f'Vehicle {action} successfully.', 'success')
    return redirect(url_for('inventory.list_vehicles'))


@inventory_bp.route('/<int:vehicle_id>/images/<int:img_id>/set-primary', methods=['POST'])
@login_required
def set_primary_image(vehicle_id, img_id):
    VehicleImage.query.filter_by(vehicle_id=vehicle_id).update({'is_primary': False})
    img = VehicleImage.query.get_or_404(img_id)
    img.is_primary = True
    db.session.commit()
    return jsonify({'success': True})


@inventory_bp.route('/<int:vehicle_id>/images/<int:img_id>/delete', methods=['POST'])
@login_required
def delete_image(vehicle_id, img_id):
    img = VehicleImage.query.get_or_404(img_id)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vehicles', img.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


@inventory_bp.route('/<int:vehicle_id>/docs/upload', methods=['POST'])
@login_required
def upload_doc(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    doc_file = request.files.get('doc_file')
    doc_type = request.form.get('doc_type', 'other')
    if doc_file and doc_file.filename and allowed_doc(doc_file.filename):
        fname = save_upload(doc_file, 'docs')
        doc = VehicleDocument(vehicle_id=vehicle_id, doc_type=doc_type,
                              filename=fname, original_name=doc_file.filename)
        db.session.add(doc)
        db.session.commit()
        flash('Document uploaded.', 'success')
    else:
        flash('Invalid file type.', 'danger')
    return redirect(url_for('inventory.view_vehicle', vehicle_id=vehicle_id))


@inventory_bp.route('/<int:vehicle_id>/docs/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_doc(vehicle_id, doc_id):
    doc = VehicleDocument.query.get_or_404(doc_id)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'docs', doc.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('inventory.view_vehicle', vehicle_id=vehicle_id))
