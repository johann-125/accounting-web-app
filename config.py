import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-2024')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'accounting.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Default admin credentials
    ADMIN_EMAIL = 'admin@company.com'
    ADMIN_PASSWORD = 'admin123'
    ADMIN_NAME = 'System Administrator'

    # App settings
    APP_NAME = 'AccounTrack'
    COMPANY_NAME = 'My Company Ltd.'
