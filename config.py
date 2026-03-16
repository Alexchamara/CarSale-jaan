import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sonnac-lanka-dev-secret-key-2026'
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'sqlite:///' + os.path.join(basedir, 'sonnac_lanka.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    PDF_LOGO_PATH = os.environ.get('PDF_LOGO_PATH', '')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_DOC_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    WTF_CSRF_ENABLED = True
