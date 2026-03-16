from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Vehicle, VehicleImage, SystemSettings, Inquiry, db, VehicleMake, VehicleModel
from sqlalchemy import or_

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    featured_vehicles = Vehicle.query.filter_by(is_featured=True, is_archived=False).filter(
        Vehicle.status != 'sold').order_by(Vehicle.updated_at.desc()).limit(8).all()
    latest_vehicles = Vehicle.query.filter_by(is_archived=False).filter(
        Vehicle.status != 'sold').order_by(Vehicle.created_at.desc()).limit(6).all()
    makes = VehicleMake.query.filter_by(is_active=True).order_by(VehicleMake.name).all()
    models = []
    body_types = [
        'Sedan', 'SUV', 'Hatchback', 'Van', 'Pickup', 'Coupe', 'Wagon', 'Minivan'
    ]
    fuel_types = ['Petrol', 'Diesel', 'Hybrid', 'Electric']
    stats = {
        'total_vehicles': Vehicle.query.filter_by(is_archived=False).filter(Vehicle.status != 'sold').count(),
        'total_sold': Vehicle.query.filter_by(status='sold').count(),
        'happy_customers': Vehicle.query.filter_by(status='sold').count(),
    }
    return render_template('public/index.html', featured_vehicles=featured_vehicles,
                           latest_vehicles=latest_vehicles, makes=makes, models=models,
                           body_types=body_types, fuel_types=fuel_types, stats=stats)


@public_bp.route('/vehicles')
def vehicles():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    query = Vehicle.query.filter_by(is_archived=False).filter(Vehicle.status != 'sold')

    make_id = request.args.get('make_id', type=int)
    make = request.args.get('make', '')  # legacy fallback
    model_q = request.args.get('model', '')
    year_min = request.args.get('year_min', type=int)
    year_max = request.args.get('year_max', type=int)
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    fuel_type = request.args.get('fuel_type', '')
    body_type = request.args.get('body_type', '')
    transmission = request.args.get('transmission', '')
    search = request.args.get('q', '')
    sort_by = request.args.get('sort', 'newest')

    if make_id:
        mk = VehicleMake.query.get(make_id)
        if mk:
            make = mk.name
    if make:
        query = query.filter(Vehicle.make == make)
    if model_q:
        query = query.filter(Vehicle.model.ilike(f'%{model_q}%'))
    if year_min:
        query = query.filter(Vehicle.year >= year_min)
    if year_max:
        query = query.filter(Vehicle.year <= year_max)
    if price_min:
        query = query.filter(Vehicle.selling_price >= price_min)
    if price_max:
        query = query.filter(Vehicle.selling_price <= price_max)
    if fuel_type:
        query = query.filter(Vehicle.fuel_type == fuel_type)
    if body_type:
        query = query.filter(Vehicle.body_type == body_type)
    if transmission:
        query = query.filter(Vehicle.transmission == transmission)
    if search:
        query = query.filter(or_(
            Vehicle.make.ilike(f'%{search}%'),
            Vehicle.model.ilike(f'%{search}%'),
            Vehicle.description.ilike(f'%{search}%'),
        ))

    sort_map = {
        'newest': Vehicle.created_at.desc(),
        'oldest': Vehicle.created_at.asc(),
        'price_asc': Vehicle.selling_price.asc(),
        'price_desc': Vehicle.selling_price.desc(),
        'year_desc': Vehicle.year.desc(),
        'year_asc': Vehicle.year.asc(),
    }
    query = query.order_by(sort_map.get(sort_by, Vehicle.created_at.desc()))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    makes_list = VehicleMake.query.filter_by(is_active=True).order_by(VehicleMake.name).all()
    models_list = VehicleModel.query.filter_by(make_id=make_id, is_active=True).order_by(VehicleModel.name).all() if make_id else []
    total = query.count() if not pagination else pagination.total

    filters = dict(make=make, make_id=make_id, model=model_q, model_id=None,
                   year_min=year_min, year_max=year_max,
                   price_min=price_min, price_max=price_max, fuel_type=fuel_type,
                   body_type=body_type, transmission=transmission, q=search, sort=sort_by)

    return render_template('public/vehicles.html', vehicles=pagination.items,
                           pagination=pagination, makes=makes_list, models=models_list, filters=filters,
                           fuel_types=['Petrol', 'Diesel', 'Hybrid', 'Electric'],
                           body_types=['Sedan', 'SUV', 'Hatchback', 'Van', 'Pickup', 'Coupe', 'Wagon', 'Minivan'],
                           transmissions=['Automatic', 'Manual', 'CVT'])


@public_bp.route('/vehicles/<int:vehicle_id>')
def vehicle_detail(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    related = Vehicle.query.filter(
        Vehicle.make == vehicle.make, Vehicle.id != vehicle.id,
        Vehicle.is_archived == False, Vehicle.status != 'sold'
    ).limit(4).all()
    return render_template('public/vehicle_detail.html', vehicle=vehicle, related=related)


@public_bp.route('/models-for-make/<int:make_id>')
def public_models_for_make(make_id):
    models = VehicleModel.query.filter_by(make_id=make_id, is_active=True).order_by(VehicleModel.name).all()
    return jsonify([{'id': m.id, 'name': m.name, 'make_id': m.make_id} for m in models])


@public_bp.route('/vehicles/<int:vehicle_id>/inquire', methods=['POST'])
def vehicle_inquire(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    inquiry = Inquiry(name=request.form.get('name'), email=request.form.get('email'),
                      phone=request.form.get('phone'), vehicle_id=vehicle_id,
                      message=request.form.get('message'))
    db.session.add(inquiry)
    db.session.commit()
    flash('Your inquiry has been submitted! We will contact you soon.', 'success')
    return redirect(url_for('public.vehicle_detail', vehicle_id=vehicle_id))


@public_bp.route('/about')
def about():
    return render_template('public/about.html')


@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        inquiry = Inquiry(name=request.form.get('name'), email=request.form.get('email'),
                          phone=request.form.get('phone'), message=request.form.get('message'))
        db.session.add(inquiry)
        db.session.commit()
        flash('Thank you for reaching out! We\'ll be in touch shortly.', 'success')
        return redirect(url_for('public.contact'))
    return render_template('public/contact.html')
