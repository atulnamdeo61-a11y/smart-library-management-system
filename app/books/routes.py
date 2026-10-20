import os
from pathlib import Path
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, current_app, abort
from flask_login import current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.book import Book
from app.models.category import Category
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.services.qr_service import QRService

books_bp = Blueprint('books', __name__)


@books_bp.route('/')
def catalog():
    """Public book catalog with search, category filtering, availability filters, and pagination."""
    query_str = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    availability = request.args.get('availability', 'all')
    sort_by = request.args.get('sort', 'title_asc')
    page = request.args.get('page', 1, type=int)
    per_page = 9

    books_query = Book.query.filter(Book.is_active == True)

    # Search filter across title, author, isbn, publisher
    if query_str:
        search_term = f"%{query_str}%"
        books_query = books_query.filter(
            or_(
                Book.title.ilike(search_term),
                Book.author.ilike(search_term),
                Book.isbn.ilike(search_term),
                Book.publisher.ilike(search_term)
            )
        )

    # Category filter
    if category_id:
        books_query = books_query.filter(Book.category_id == category_id)

    # Availability filter
    if availability == 'available':
        books_query = books_query.filter(Book.available_copies > 0)
    elif availability == 'unavailable':
        books_query = books_query.filter(Book.available_copies == 0)

    # Sorting
    if sort_by == 'title_desc':
        books_query = books_query.order_by(Book.title.desc())
    elif sort_by == 'author_asc':
        books_query = books_query.order_by(Book.author.asc())
    elif sort_by == 'year_desc':
        books_query = books_query.order_by(Book.publication_year.desc().nullslast())
    elif sort_by == 'newest':
        books_query = books_query.order_by(Book.created_at.desc())
    else:  # default title_asc
        books_query = books_query.order_by(Book.title.asc())

    pagination = books_query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.order_by(Category.name.asc()).all()

    return render_template(
        'books/catalog.html',
        books=pagination.items,
        pagination=pagination,
        categories=categories,
        current_category=category_id,
        current_query=query_str,
        current_availability=availability,
        current_sort=sort_by
    )


@books_bp.route('/<int:book_id>')
def detail(book_id):
    """Book detail view with description, copies, QR code, and student action buttons."""
    book = Book.query.get_or_404(book_id)

    # Ensure QR code exists
    if not book.qr_code_path or not (Path(current_app.config['QR_FOLDER']) / f"book_{book.id}.png").exists():
        QRService.generate_qr_for_book(book)
        db.session.commit()

    # Check student loan / request status for UI state
    user_has_loan = False
    user_has_pending_request = False
    if current_user.is_authenticated and current_user.is_student:
        user_has_loan = BookLoan.query.filter_by(
            student_id=current_user.id,
            book_id=book.id,
            status=BookLoan.STATUS_ACTIVE
        ).first() is not None
        user_has_pending_request = BookRequest.query.filter_by(
            student_id=current_user.id,
            book_id=book.id,
            status=BookRequest.STATUS_PENDING
        ).first() is not None

    # Related books in the same category
    related_books = Book.query.filter(
        Book.category_id == book.category_id,
        Book.id != book.id,
        Book.is_active == True
    ).limit(3).all()

    return render_template(
        'books/detail.html',
        book=book,
        user_has_loan=user_has_loan,
        user_has_pending_request=user_has_pending_request,
        related_books=related_books
    )


@books_bp.route('/<int:book_id>/qr')
def qr_view(book_id):
    """Printable / full-screen QR code page for library shelf labeling."""
    book = Book.query.get_or_404(book_id)
    if not book.qr_code_path or not (Path(current_app.config['QR_FOLDER']) / f"book_{book.id}.png").exists():
        QRService.generate_qr_for_book(book)
        db.session.commit()

    return render_template('books/qr_view.html', book=book)


@books_bp.route('/<int:book_id>/qr/download')
def qr_download(book_id):
    """Download the high-resolution QR code PNG image."""
    book = Book.query.get_or_404(book_id)
    qr_file = Path(current_app.config['QR_FOLDER']) / f"book_{book.id}.png"
    if not qr_file.exists():
        QRService.generate_qr_for_book(book)
        db.session.commit()

    return send_file(
        str(qr_file),
        mimetype='image/png',
        as_attachment=True,
        download_name=f"QR_{book.isbn or book.id}_{secure_filename(book.title)}.png"
    )
