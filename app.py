import os
from flask import Flask
from config import Config
from models import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload folders exist
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'vehicles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'docs'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'logos'), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from routes.public import public_bp
    from routes.auth import auth_bp
    from routes.inventory import inventory_bp
    from routes.costing import costing_bp
    from routes.quotations import quotations_bp
    from routes.sales import sales_bp
    from routes.customers import customers_bp
    from routes.reports import reports_bp
    from routes.users import users_bp
    from routes.settings import settings_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/admin/inventory')
    app.register_blueprint(costing_bp, url_prefix='/admin/costing')
    app.register_blueprint(quotations_bp, url_prefix='/admin/quotations')
    app.register_blueprint(sales_bp, url_prefix='/admin/sales')
    app.register_blueprint(customers_bp, url_prefix='/admin/customers')
    app.register_blueprint(reports_bp, url_prefix='/admin/reports')
    app.register_blueprint(users_bp, url_prefix='/admin/users')
    app.register_blueprint(settings_bp, url_prefix='/admin/settings')

    # Admin home redirect
    from flask import redirect, url_for
    from flask_login import login_required

    @app.route('/admin')
    @login_required
    def admin_home():
        return redirect(url_for('reports.dashboard'))

    # Jinja2 globals
    from models import SystemSettings, Inquiry
    @app.context_processor
    def inject_globals():
        settings = SystemSettings.query.first()
        unread_inquiries = Inquiry.query.filter_by(is_read=False).count()
        return dict(settings=settings, unread_inquiries=unread_inquiries)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        # Create default settings if not exist
        from models import SystemSettings
        if not SystemSettings.query.first():
            s = SystemSettings()
            db.session.add(s)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000)
