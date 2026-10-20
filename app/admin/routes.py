import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename
from app.extensions import db
from app.auth.decorators import admin_required
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.models.fine import Fine
from app.models.id_card import StudentIdCard
from app.models.audit_log import AuditLog
from app.books.forms import BookForm, CategoryForm
from app.services.circulation_service import CirculationService
from app.services.fine_service import FineService
from app.services.qr_service import QRService
from app.services.analytics_service import AnalyticsService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin executive dashboard with complete library analytics, Chart.js metrics, and recent events."""
    metrics = AnalyticsService.get_dashboard_metrics()
    chart_data = AnalyticsService.get_chart_data()
    recent_activity = AnalyticsService.get_recent_activity(limit=8)
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    return render_template(
        'admin/dashboard.html',
        metrics=metrics,
        chart_data=chart_data,
        recent_activity=recent_activity,
        recent_logs=recent_logs,
        today=date.today()
    )


# ==========================================
# BOOKS CRUD
# ==========================================

@admin_bp.route('/books')
@admin_required
def books_list():
    """Manage books table with filtering, stock indicators, and actions."""
    query_str = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    page = request.args.get('page', 1, type=int)

    query = Book.query
    if query_str:
        search = f"%{query_str}%"
        query = query.filter(
            (Book.title.ilike(search)) | (Book.author.ilike(search)) | (Book.isbn.ilike(search))
        )
    if category_id:
        query = query.filter_by(category_id=category_id)

    pagination = query.order_by(Book.id.desc()).paginate(page=page, per_page=10, error_out=False)
    categories = Category.query.order_by(Category.name.asc()).all()

    return render_template(
        'admin/books_list.html',
        books=pagination.items,
        pagination=pagination,
        categories=categories,
        current_query=query_str,
        current_category=category_id
    )


@admin_bp.route('/books/new', methods=['GET', 'POST'])
@admin_required
def book_new():
    """Add a new book to the library catalog with QR generation."""
    form = BookForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name.asc()).all()]

    if form.validate_on_submit():
        try:
            # Handle cover image upload if present
            cover_filename = None
            if form.cover_image.data:
                file = form.cover_image.data
                ext = file.filename.rsplit('.', 1)[1].lower()
                clean_name = f"cover_{secure_filename(form.title.data[:20])}_{int(datetime.utcnow().timestamp())}.{ext}"
                upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
                upload_dir.mkdir(parents=True, exist_ok=True)
                file.save(str(upload_dir / clean_name))
                cover_filename = f"uploads/{clean_name}"

            book = Book(
                title=form.title.data.strip(),
                author=form.author.data.strip(),
                isbn=form.isbn.data.strip() if form.isbn.data else None,
                category_id=form.category_id.data,
                publisher=form.publisher.data.strip() if form.publisher.data else None,
                publication_year=form.publication_year.data,
                shelf_location=form.shelf_location.data.strip() if form.shelf_location.data else None,
                total_copies=form.total_copies.data,
                available_copies=form.available_copies.data if form.available_copies.data is not None else form.total_copies.data,
                description=form.description.data.strip() if form.description.data else None,
                cover_image_path=cover_filename,
                is_active=True
            )
            db.session.add(book)
            db.session.flush()

            # Generate QR code immediately
            QRService.generate_qr_for_book(book)

            AuditLog.record(
                actor_id=current_user.id,
                action='CREATE_BOOK',
                entity_type='Book',
                entity_id=book.id,
                details=f"Admin added new book '{book.title}' (ISBN: {book.isbn}, Copies: {book.total_copies})"
            )
            db.session.commit()

            flash(f"Book '{book.title}' added successfully with unique QR code!", 'success')
            return redirect(url_for('admin.books_list'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating book: {str(e)}", 'danger')

    return render_template('admin/book_form.html', form=form, title="Add New Book")


@admin_bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@admin_required
def book_edit(book_id):
    """Edit existing book details and stock levels."""
    book = Book.query.get_or_404(book_id)
    form = BookForm(original_book_id=book.id, obj=book)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name.asc()).all()]

    if form.validate_on_submit():
        try:
            # Handle new cover image upload
            if form.cover_image.data:
                file = form.cover_image.data
                ext = file.filename.rsplit('.', 1)[1].lower()
                clean_name = f"cover_{book.id}_{int(datetime.utcnow().timestamp())}.{ext}"
                upload_dir = Path(current_app.config['UPLOAD_FOLDER'])
                upload_dir.mkdir(parents=True, exist_ok=True)
                file.save(str(upload_dir / clean_name))
                book.cover_image_path = f"uploads/{clean_name}"

            # Check difference in copies
            copy_delta = form.total_copies.data - book.total_copies
            book.title = form.title.data.strip()
            book.author = form.author.data.strip()
            book.isbn = form.isbn.data.strip() if form.isbn.data else None
            book.category_id = form.category_id.data
            book.publisher = form.publisher.data.strip() if form.publisher.data else None
            book.publication_year = form.publication_year.data
            book.shelf_location = form.shelf_location.data.strip() if form.shelf_location.data else None
            book.total_copies = form.total_copies.data

            # Adjust available copies based on total_copies delta
            if form.available_copies.data is not None:
                book.available_copies = form.available_copies.data
            else:
                book.available_copies = max(0, book.available_copies + copy_delta)

            book.description = form.description.data.strip() if form.description.data else None

            # Regenerate QR code if needed
            QRService.generate_qr_for_book(book)

            AuditLog.record(
                actor_id=current_user.id,
                action='UPDATE_BOOK',
                entity_type='Book',
                entity_id=book.id,
                details=f"Admin updated book details for '{book.title}'."
            )
            db.session.commit()

            flash(f"Book '{book.title}' updated successfully.", 'success')
            return redirect(url_for('admin.books_list'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating book: {str(e)}", 'danger')

    return render_template('admin/book_form.html', form=form, title=f"Edit Book: {book.title}", book=book)


@admin_bp.route('/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def book_delete(book_id):
    """
    Safely delete a book:
    Blocks deletion if there are active loans.
    Uses soft-deletion if past circulation records exist to preserve history.
    """
    book = Book.query.get_or_404(book_id)

    # 1. Check for active loans
    active_loans = BookLoan.query.filter_by(book_id=book.id, status=BookLoan.STATUS_ACTIVE).count()
    if active_loans > 0:
        flash(f"Cannot delete book: '{book.title}' has {active_loans} currently active loan(s). Return them first.", 'danger')
        return redirect(url_for('admin.books_list'))

    # 2. Check for historical circulation records
    historical_loans = BookLoan.query.filter_by(book_id=book.id).count()
    historical_requests = BookRequest.query.filter_by(book_id=book.id).count()

    try:
        if historical_loans > 0 or historical_requests > 0:
            # Soft delete to preserve historical integrity
            book.is_active = False
            book.available_copies = 0
            AuditLog.record(
                actor_id=current_user.id,
                action='SOFT_DELETE_BOOK',
                entity_type='Book',
                entity_id=book.id,
                details=f"Soft deleted book '{book.title}' because it has {historical_loans} past loans."
            )
            flash(f"Book '{book.title}' has past circulation records and was safely deactivated.", 'warning')
        else:
            # Hard delete if no history
            db.session.delete(book)
            AuditLog.record(
                actor_id=current_user.id,
                action='DELETE_BOOK',
                entity_type='Book',
                entity_id=book_id,
                details=f"Permanently deleted book '{book.title}'."
            )
            flash(f"Book '{book.title}' was permanently deleted.", 'success')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete book: {str(e)}", 'danger')

    return redirect(url_for('admin.books_list'))


# ==========================================
# CATEGORIES MANAGEMENT
# ==========================================

@admin_bp.route('/categories', methods=['GET', 'POST'])
@admin_required
def categories_list():
    """List, create, and manage book categories."""
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = Category.query.filter(Category.name.ilike(name)).first()
        if existing:
            flash(f"Category '{name}' already exists.", 'warning')
        else:
            cat = Category(name=name, description=form.description.data.strip() if form.description.data else None)
            db.session.add(cat)
            db.session.commit()
            AuditLog.record(
                actor_id=current_user.id,
                action='CREATE_CATEGORY',
                entity_type='Category',
                entity_id=cat.id,
                details=f"Created category '{name}'."
            )
            db.session.commit()
            flash(f"Category '{name}' created successfully.", 'success')
            return redirect(url_for('admin.categories_list'))

    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template('admin/categories.html', categories=categories, form=form)


# ==========================================
# USER & STAFF MANAGEMENT
# ==========================================

@admin_bp.route('/users')
@admin_required
def users_list():
    """View and manage student and staff accounts."""
    role_filter = request.args.get('role', 'all')
    query = User.query

    if role_filter in ('student', 'librarian', 'admin'):
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users_list.html', users=users, current_role=role_filter)


@admin_bp.route('/librarians/new', methods=['GET', 'POST'])
@admin_required
def librarian_new():
    """Create a new librarian staff account."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if not full_name or not email or not password:
            flash('All required fields must be filled.', 'danger')
            return redirect(url_for('admin.librarian_new'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('admin.librarian_new'))

        existing = User.query.filter(User.email.ilike(email)).first()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return redirect(url_for('admin.librarian_new'))

        try:
            lib_user = User(
                full_name=full_name,
                email=email,
                role='librarian',
                phone=phone,
                is_active=True
            )
            lib_user.set_password(password)
            db.session.add(lib_user)
            db.session.flush()

            AuditLog.record(
                actor_id=current_user.id,
                action='CREATE_LIBRARIAN',
                entity_type='User',
                entity_id=lib_user.id,
                details=f"Admin created librarian account for '{full_name}' ({email})."
            )
            db.session.commit()
            flash(f"Librarian account for '{full_name}' created successfully.", 'success')
            return redirect(url_for('admin.users_list', role='librarian'))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to create librarian: {str(e)}", 'danger')

    return render_template('admin/librarian_form.html')


@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Activate or deactivate a user account."""
    if user_id == current_user.id:
        flash('You cannot deactivate your own administrative account.', 'warning')
        return redirect(url_for('admin.users_list'))

    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    action_str = "activated" if user.is_active else "deactivated"

    AuditLog.record(
        actor_id=current_user.id,
        action='TOGGLE_USER_STATUS',
        entity_type='User',
        entity_id=user.id,
        details=f"User {user.email} was {action_str}."
    )
    db.session.commit()

    flash(f"Account for {user.full_name} has been {action_str}.", 'info')
    return redirect(request.referrer or url_for('admin.users_list'))


# ==========================================
# CIRCULATION & REQUESTS MANAGEMENT
# ==========================================

@admin_bp.route('/requests')
@admin_required
def requests_list():
    """All student borrow requests."""
    status_filter = request.args.get('status', 'Pending')
    query = BookRequest.query
    if status_filter != 'All':
        query = query.filter_by(status=status_filter)
    requests = query.order_by(BookRequest.requested_at.desc()).all()
    return render_template('admin/requests.html', requests=requests, current_status=status_filter)


@admin_bp.route('/requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_request(request_id):
    success, message = CirculationService.approve_request(current_user, request_id)
    flash(message, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('admin.requests_list'))


@admin_bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_request(request_id):
    remarks = request.form.get('remarks', 'Rejected by administrator')
    success, message = CirculationService.reject_request(current_user, request_id, remarks)
    flash(message, 'info' if success else 'danger')
    return redirect(request.referrer or url_for('admin.requests_list'))


@admin_bp.route('/loans')
@admin_required
def loans_list():
    status_filter = request.args.get('status', 'Active')
    query = BookLoan.query
    if status_filter != 'All':
        query = query.filter_by(status=status_filter)
    loans = query.order_by(BookLoan.issue_date.desc()).all()
    return render_template('admin/loans.html', loans=loans, current_status=status_filter, today=date.today())


@admin_bp.route('/overdue')
@admin_required
def overdue_list():
    overdue_loans = BookLoan.query.filter(
        BookLoan.status == BookLoan.STATUS_ACTIVE,
        BookLoan.due_date < date.today()
    ).order_by(BookLoan.due_date.asc()).all()

    for loan in overdue_loans:
        FineService.refresh_loan_fine(loan)
    db.session.commit()

    return render_template('admin/overdue.html', loans=overdue_loans, today=date.today())


# ==========================================
# FINES & PAYMENTS MANAGEMENT
# ==========================================

@admin_bp.route('/fines')
@admin_required
def fines_list():
    status_filter = request.args.get('status', 'Unpaid')
    query = Fine.query.join(BookLoan)

    if status_filter == 'Unpaid':
        query = query.filter(Fine.payment_status.in_([Fine.STATUS_PENDING, Fine.STATUS_PARTIALLY_PAID]))
    elif status_filter == 'Paid':
        query = query.filter(Fine.payment_status == Fine.STATUS_PAID)
    elif status_filter == 'Waived':
        query = query.filter(Fine.payment_status == Fine.STATUS_WAIVED)

    fines = query.order_by(Fine.updated_at.desc()).all()
    return render_template('admin/fines.html', fines=fines, current_status=status_filter)


@admin_bp.route('/fines/<int:fine_id>/pay', methods=['POST'])
@admin_required
def record_payment(fine_id):
    amount = request.form.get('amount')
    method = request.form.get('payment_method', 'Cash')
    note = request.form.get('reference_note', '')

    success, message = FineService.record_payment(
        fine_id=fine_id,
        staff_user=current_user,
        amount=amount,
        payment_method=method,
        reference_note=note
    )
    flash(message, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('admin.fines_list'))


@admin_bp.route('/fines/<int:fine_id>/waive', methods=['POST'])
@admin_required
def waive_fine(fine_id):
    reason = request.form.get('reason', 'Administrative decision')
    success, message = FineService.waive_fine(fine_id, current_user, reason)
    flash(message, 'info' if success else 'danger')
    return redirect(request.referrer or url_for('admin.fines_list'))


# ==========================================
# REPORTS & AUDIT LOGS & SETTINGS
# ==========================================

@admin_bp.route('/reports')
@admin_required
def reports():
    metrics = AnalyticsService.get_dashboard_metrics()
    chart_data = AnalyticsService.get_chart_data()

    # Category statistics
    category_stats = db.session.query(
        Category.name,
        func.count(Book.id).label('book_count'),
        func.coalesce(func.sum(Book.total_copies), 0).label('total_copies'),
        func.coalesce(func.sum(Book.available_copies), 0).label('available_copies')
    ).outerjoin(Book, Book.category_id == Category.id).group_by(Category.name).all()

    return render_template(
        'admin/reports.html',
        metrics=metrics,
        chart_data=chart_data,
        category_stats=category_stats,
        today=date.today()
    )


@admin_bp.route('/audit-logs')
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '').strip()

    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('admin/audit_logs.html', logs=pagination.items, pagination=pagination, current_action=action_filter)


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        borrow_days = request.form.get('borrow_days', type=int)
        fine_rate = request.form.get('fine_rate', type=float)
        max_loans = request.form.get('max_loans', type=int)
        id_card_fee = request.form.get('id_card_fee', type=float)
        upi_id = request.form.get('upi_id', '').strip()
        upi_payee_name = request.form.get('upi_payee_name', '').strip()

        if borrow_days and borrow_days > 0:
            current_app.config['DEFAULT_BORROW_DAYS'] = borrow_days
        if fine_rate is not None and fine_rate >= 0:
            current_app.config['FINE_RATE_PER_DAY'] = fine_rate
        if max_loans and max_loans > 0:
            current_app.config['MAX_ACTIVE_LOANS_PER_STUDENT'] = max_loans
        if id_card_fee is not None and id_card_fee >= 0:
            current_app.config['ID_CARD_FEE'] = id_card_fee
        if upi_id:
            current_app.config['UPI_ID'] = upi_id
        if upi_payee_name:
            current_app.config['UPI_PAYEE_NAME'] = upi_payee_name

        AuditLog.record(
            actor_id=current_user.id,
            action='UPDATE_SETTINGS',
            entity_type='SystemConfig',
            details=f"Updated settings: BorrowDays={borrow_days}, FineRate=₹{fine_rate}/day, MaxLoans={max_loans}, IDCardFee=₹{id_card_fee}, UPI_ID={upi_id}"
        )
        db.session.commit()
        flash('System configuration rules updated successfully.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template(
        'admin/settings.html',
        borrow_days=current_app.config.get('DEFAULT_BORROW_DAYS', 14),
        fine_rate=current_app.config.get('FINE_RATE_PER_DAY', 2.00),
        max_loans=current_app.config.get('MAX_ACTIVE_LOANS_PER_STUDENT', 3),
        id_card_fee=current_app.config.get('ID_CARD_FEE', 50.00),
        upi_id=current_app.config.get('UPI_ID', 'smartlibrary@upi'),
        upi_payee_name=current_app.config.get('UPI_PAYEE_NAME', 'Smart College Library'),
        currency_symbol=current_app.config.get('CURRENCY_SYMBOL', '₹')
    )


# ==========================================
# ADMIN STUDENT ID CARD MANAGEMENT
# ==========================================

@admin_bp.route('/id-cards')
@admin_required
def id_cards_list():
    """Admin view of all student ID card applications and issued cards."""
    status_filter = request.args.get('status', 'All')
    payment_filter = request.args.get('payment', 'All')
    search_query = request.args.get('q', '').strip()

    query = StudentIdCard.query.join(User, StudentIdCard.student_id == User.id)

    if status_filter in ('Pending', 'Approved', 'Rejected'):
        query = query.filter(StudentIdCard.status == status_filter)
    if payment_filter in ('Pending', 'Paid', 'Waived'):
        query = query.filter(StudentIdCard.payment_status == payment_filter)

    if search_query:
        query = query.filter(
            db.or_(
                StudentIdCard.card_number.ilike(f"%{search_query}%"),
                StudentIdCard.roll_number.ilike(f"%{search_query}%"),
                StudentIdCard.course_branch.ilike(f"%{search_query}%"),
                StudentIdCard.payment_reference.ilike(f"%{search_query}%"),
                User.full_name.ilike(f"%{search_query}%"),
                User.email.ilike(f"%{search_query}%")
            )
        )

    cards = query.order_by(StudentIdCard.created_at.desc()).all()

    # Metrics
    total_count = StudentIdCard.query.count()
    pending_count = StudentIdCard.query.filter_by(status=StudentIdCard.STATUS_PENDING).count()
    approved_count = StudentIdCard.query.filter_by(status=StudentIdCard.STATUS_APPROVED).count()
    rejected_count = StudentIdCard.query.filter_by(status=StudentIdCard.STATUS_REJECTED).count()
    total_fees_collected = db.session.query(db.func.sum(StudentIdCard.fee_amount)).filter(
        StudentIdCard.payment_status.in_([StudentIdCard.PAYMENT_PAID, StudentIdCard.PAYMENT_WAIVED])
    ).scalar() or Decimal('0.00')

    return render_template(
        'librarian/id_cards.html',
        cards=cards,
        current_status=status_filter,
        current_payment=payment_filter,
        search_query=search_query,
        total_count=total_count,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        total_fees_collected=total_fees_collected,
        bp_prefix='admin'
    )


@admin_bp.route('/id-cards/new', methods=['GET', 'POST'])
@admin_required
def id_card_create():
    """Admin direct issuance of a student ID card."""
    students = User.query.filter_by(role=User.ROLE_STUDENT, is_active=True).order_by(User.full_name.asc()).all()

    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        student = User.query.get_or_404(student_id)
        course_branch = request.form.get('course_branch', '').strip()
        academic_year = request.form.get('academic_year', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        dob_str = request.form.get('dob', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()
        address = request.form.get('address', '').strip()
        payment_status = request.form.get('payment_status', StudentIdCard.PAYMENT_PAID)
        payment_method = request.form.get('payment_method', 'Cash')
        payment_reference = request.form.get('payment_reference', '').strip()
        validity_years = request.form.get('validity_years', 3, type=int)

        if not course_branch or not academic_year:
            flash('Course/Branch and Academic Year are mandatory.', 'danger')
            return render_template('librarian/id_card_form.html', students=students, bp_prefix='admin')

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        photo_file = request.files.get('id_photo')
        photo_path = student.profile_image

        if photo_file and photo_file.filename:
            raw_ext = Path(photo_file.filename).suffix.lower()
            if raw_ext in ('.png', '.jpg', '.jpeg', '.webp'):
                clean_name = f"idphoto_{student.id}_{uuid.uuid4().hex[:8]}{raw_ext}"
                avatars_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'avatars'
                avatars_dir.mkdir(parents=True, exist_ok=True)
                dest = avatars_dir / clean_name
                photo_file.save(str(dest))
                photo_path = f"uploads/avatars/{clean_name}"
                if not student.profile_image:
                    student.profile_image = photo_path

        card_number = StudentIdCard.generate_card_number(student.student_id or str(student.id))
        fee = Decimal(str(current_app.config.get('ID_CARD_FEE', 50.00)))

        existing_card = StudentIdCard.query.filter_by(student_id=student.id).order_by(StudentIdCard.id.desc()).first()
        if existing_card and existing_card.status != StudentIdCard.STATUS_APPROVED:
            card = existing_card
            card.course_branch = course_branch
            card.academic_year = academic_year
            card.blood_group = blood_group
            card.dob = dob
            card.emergency_contact = emergency_contact
            card.address = address
            if photo_path:
                card.photo_path = photo_path
            card.payment_status = payment_status
            card.payment_method = payment_method
            card.payment_reference = payment_reference or ('ADMIN-DIRECT-ISSUE' if payment_status != StudentIdCard.PAYMENT_PENDING else None)
            card.paid_at = datetime.utcnow() if payment_status in (StudentIdCard.PAYMENT_PAID, StudentIdCard.PAYMENT_WAIVED) else None
        else:
            card = StudentIdCard(
                student_id=student.id,
                roll_number=student.student_id or f"STU{student.id:04d}",
                course_branch=course_branch,
                academic_year=academic_year,
                blood_group=blood_group,
                dob=dob,
                emergency_contact=emergency_contact,
                address=address,
                photo_path=photo_path,
                card_number=card_number,
                fee_amount=fee,
                payment_status=payment_status,
                payment_method=payment_method,
                payment_reference=payment_reference or ('ADMIN-DIRECT-ISSUE' if payment_status != StudentIdCard.PAYMENT_PENDING else None),
                paid_at=datetime.utcnow() if payment_status in (StudentIdCard.PAYMENT_PAID, StudentIdCard.PAYMENT_WAIVED) else None
            )
            db.session.add(card)
            db.session.flush()

        card.approve(staff_user_id=current_user.id, validity_years=validity_years)
        QRService.generate_id_card_qr(card)

        AuditLog.record(
            actor_id=current_user.id,
            action='DIRECT_ISSUE_ID_CARD',
            entity_type='StudentIdCard',
            entity_id=card.id,
            details=f"Admin {current_user.email} directly created and approved Student ID card {card.card_number} for {student.email}."
        )
        db.session.commit()

        flash(f"Student ID Card {card.card_number} created and approved successfully!", 'success')
        return redirect(url_for('admin.id_card_view', card_id=card.id))

    return render_template('librarian/id_card_form.html', students=students, bp_prefix='admin')


@admin_bp.route('/id-cards/<int:card_id>/approve', methods=['POST'])
@admin_required
def id_card_approve(card_id):
    """Admin approve a student ID card."""
    card = StudentIdCard.query.get_or_404(card_id)
    validity_years = request.form.get('validity_years', 3, type=int)

    card.approve(staff_user_id=current_user.id, validity_years=validity_years)
    if card.payment_status == StudentIdCard.PAYMENT_PENDING:
        card.payment_status = StudentIdCard.PAYMENT_PAID
        card.paid_at = datetime.utcnow()

    QRService.generate_id_card_qr(card)

    AuditLog.record(
        actor_id=current_user.id,
        action='APPROVE_ID_CARD',
        entity_type='StudentIdCard',
        entity_id=card.id,
        details=f"Admin {current_user.email} approved Student ID card {card.card_number} for {card.student.email}."
    )
    db.session.commit()

    flash(f"Student ID Card {card.card_number} approved and issued successfully!", 'success')
    return redirect(request.referrer or url_for('admin.id_cards_list'))


@admin_bp.route('/id-cards/<int:card_id>/reject', methods=['POST'])
@admin_required
def id_card_reject(card_id):
    """Admin reject a student ID card application."""
    card = StudentIdCard.query.get_or_404(card_id)
    remarks = request.form.get('rejection_remarks', '').strip()
    if not remarks:
        remarks = 'Information provided could not be verified or photo is unclear. Please update and re-submit.'

    card.reject(staff_user_id=current_user.id, remarks=remarks)

    AuditLog.record(
        actor_id=current_user.id,
        action='REJECT_ID_CARD',
        entity_type='StudentIdCard',
        entity_id=card.id,
        details=f"Admin {current_user.email} rejected Student ID card application {card.card_number}. Remarks: {remarks}"
    )
    db.session.commit()

    flash(f"Student ID Card application {card.card_number} was rejected.", 'warning')
    return redirect(request.referrer or url_for('admin.id_cards_list'))


@admin_bp.route('/id-cards/<int:card_id>/view')
@admin_required
def id_card_view(card_id):
    """Admin view of a student ID card."""
    card = StudentIdCard.query.get_or_404(card_id)
    if card.is_approved and not card.qr_code_path:
        QRService.generate_id_card_qr(card)
        db.session.commit()
    return render_template('librarian/id_card_view.html', card=card, bp_prefix='admin')


@admin_bp.route('/id-cards/<int:card_id>/print')
@admin_required
def id_card_print(card_id):
    """Admin printable view for a student ID card."""
    card = StudentIdCard.query.get_or_404(card_id)
    if not card.qr_code_path:
        QRService.generate_id_card_qr(card)
        db.session.commit()
    return render_template('student/id_card_print.html', card=card)
