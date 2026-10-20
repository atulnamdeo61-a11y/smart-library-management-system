import os
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
from flask_login import current_user
from config import config_by_name
from app.extensions import db, login_manager, migrate, csrf


def create_app(config_name=None):
    """Application factory for the Smart Library Management System."""
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Ensure upload and QR code asset folders exist
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    Path(app.config['QR_FOLDER']).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Register blueprints
    from app.auth import auth_bp
    from app.books import books_bp
    from app.student import student_bp
    from app.admin import admin_bp
    from app.librarian import librarian_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(books_bp, url_prefix='/books')
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(librarian_bp)

    # Register CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(app)

    # Public Root & About Routes
    @app.route('/')
    def index():
        from app.models.book import Book
        from app.models.category import Category
        featured_books = Book.query.filter(Book.is_active == True).order_by(Book.id.desc()).limit(6).all()
        categories = Category.query.order_by(Category.name.asc()).limit(8).all()
        total_books = Book.query.filter(Book.is_active == True).count()
        return render_template('index.html', featured_books=featured_books, categories=categories, total_books=total_books)

    @app.route('/about')
    def about():
        return render_template('about.html')

    # Global Context Processors for Templates
    @app.context_processor
    def inject_global_template_data():
        from app.models.book_request import BookRequest
        from app.models.book_loan import BookLoan
        from app.models.id_card import StudentIdCard
        
        pending_requests_count = 0
        overdue_loans_count = 0
        pending_id_cards_count = 0
        if current_user.is_authenticated:
            if current_user.is_staff:
                pending_requests_count = BookRequest.query.filter_by(status=BookRequest.STATUS_PENDING).count()
                pending_id_cards_count = StudentIdCard.query.filter_by(status=StudentIdCard.STATUS_PENDING).count()
                overdue_loans_count = BookLoan.query.filter(
                    BookLoan.status == BookLoan.STATUS_ACTIVE,
                    BookLoan.due_date < date.today()
                ).count()
            elif current_user.is_student:
                overdue_loans_count = BookLoan.query.filter(
                    BookLoan.student_id == current_user.id,
                    BookLoan.status == BookLoan.STATUS_ACTIVE,
                    BookLoan.due_date < date.today()
                ).count()

        return {
            'currency_symbol': app.config.get('CURRENCY_SYMBOL', '₹'),
            'today': date.today(),
            'current_year': datetime.utcnow().year,
            'pending_requests_badge': pending_requests_count,
            'pending_id_cards_badge': pending_id_cards_count,
            'overdue_loans_badge': overdue_loans_count,
            'app_name': 'Smart Library'
        }

    # Custom HTTP Error Handlers (Section 17)
    @app.errorhandler(400)
    def bad_request_error(error):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
