# Copyright (c) 2026 Atul Namdeo (GitHub: @atulnamdeo61-a11y). All Rights Reserved.
# Proprietary and Personal Academic Project. Strictly NOT Open-Source Software.
# Unauthorized copying, distribution, or plagiarism is strictly prohibited.

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = Path(__file__).resolve().parent
load_dotenv(basedir / '.env')


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'smart-lib-dev-key-should-be-overridden-in-production-2026')
    
    # Database configuration: defaults to SQLite if MySQL/PostgreSQL is not specified or for easy start
    _raw_db_url = os.getenv('DATABASE_URL', f"sqlite:///{basedir / 'smart_library.db'}")
    if _raw_db_url and _raw_db_url.startswith('postgres://'):
        _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    } if ('mysql' in _raw_db_url or 'postgresql' in _raw_db_url) else {}

    # File uploads and media
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    UPLOAD_FOLDER = str(basedir / 'app' / 'static' / 'uploads')
    QR_FOLDER = str(basedir / 'app' / 'static' / 'qrcodes')

    # Library circulation rules
    DEFAULT_BORROW_DAYS = int(os.getenv('DEFAULT_BORROW_DAYS', 14))
    MAX_ACTIVE_LOANS_PER_STUDENT = int(os.getenv('MAX_ACTIVE_LOANS_PER_STUDENT', 3))
    FINE_RATE_PER_DAY = float(os.getenv('FINE_RATE_PER_DAY', 2.00))
    FINE_GRACE_PERIOD_DAYS = int(os.getenv('FINE_GRACE_PERIOD_DAYS', 0))
    CURRENCY_SYMBOL = os.getenv('CURRENCY_SYMBOL', '₹')
    REQUIRE_LIBRARIAN_APPROVAL = os.getenv('REQUIRE_LIBRARIAN_APPROVAL', 'True').lower() in ('true', '1', 'yes')

    # Security & session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Email & Gmail SMTP Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME', 'smartlibrary.system@gmail.com'))

    # Student ID Card & Dynamic UPI QR Configuration
    ID_CARD_FEE = float(os.getenv('ID_CARD_FEE', 50.00))
    UPI_ID = os.getenv('UPI_ID', 'smartlibrary@upi')
    UPI_PAYEE_NAME = os.getenv('UPI_PAYEE_NAME', 'Smart College Library')

    # Google Gemini AI Integration (Course & Syllabus Book Recommendations)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite').strip()


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration (isolated in-memory database)."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
