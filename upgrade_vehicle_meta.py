"""One-off helper to create vehicle meta tables, add FK columns, and backfill data.

Usage (after activating venv):
  FLASK_APP=app:create_app python upgrade_vehicle_meta.py

Safe to re-run; skips existing columns and rows.
"""
from app import create_app
from models import db, Vehicle, VehicleMake, VehicleModel
from sqlalchemy import inspect, text


def ensure_columns(engine):
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('vehicles')}
    with engine.begin() as conn:
        if 'make_id' not in cols:
            conn.execute(text('ALTER TABLE vehicles ADD COLUMN make_id INTEGER'))
        if 'model_id' not in cols:
            conn.execute(text('ALTER TABLE vehicles ADD COLUMN model_id INTEGER'))


def create_tables():
    VehicleMake.__table__.create(db.engine, checkfirst=True)
    VehicleModel.__table__.create(db.engine, checkfirst=True)


def backfill():
    make_cache = {m.name.lower(): m for m in VehicleMake.query.all()}
    model_cache = {}

    vehicles = Vehicle.query.all()
    for v in vehicles:
        make_name = (v.make or '').strip()
        model_name = (v.model or '').strip()
        if not make_name or not model_name:
            continue

        mk = make_cache.get(make_name.lower())
        if not mk:
            mk = VehicleMake(name=make_name)
            db.session.add(mk)
            db.session.flush()
            make_cache[make_name.lower()] = mk

        key = (mk.id, model_name.lower())
        mdl = model_cache.get(key)
        if not mdl:
            mdl = VehicleModel.query.filter_by(make_id=mk.id, name=model_name).first()
            if not mdl:
                mdl = VehicleModel(make_id=mk.id, name=model_name)
                db.session.add(mdl)
                db.session.flush()
            model_cache[key] = mdl

        if not v.make_id:
            v.make_id = mk.id
        if not v.model_id:
            v.model_id = mdl.id
    db.session.commit()


def main():
    app = create_app()
    with app.app_context():
        ensure_columns(db.engine)
        create_tables()
        backfill()
        print('Vehicle metadata upgrade complete.')


if __name__ == '__main__':
    main()
