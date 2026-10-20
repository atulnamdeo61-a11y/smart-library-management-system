from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import current_user
from app.extensions import db
from app.auth.decorators import staff_required
from app.models.book import Book
from app.models.user import User
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.models.fine import Fine
from app.models.id_card import StudentIdCard
from app.models.audit_log import AuditLog
from app.services.circulation_service import CirculationService
from app.services.fine_service import FineService
from app.services.analytics_service import AnalyticsService
from app.services.qr_service import QRService

librarian_bp = Blueprint('librarian', __name__, url_prefix='/librarian')


@librarian_bp.route('/dashboard')
@staff_required
def dashboard():
    """Librarian overview dashboard with pending actions, circulation stats, and quick links."""
    metrics = AnalyticsService.get_dashboard_metrics()
    pending_requests = BookRequest.query.filter_by(
        status=BookRequest.STATUS_PENDING
    ).order_by(BookRequest.requested_at.asc()).limit(5).all()

    overdue_loans = BookLoan.query.filter(
        BookLoan.status == BookLoan.STATUS_ACTIVE,
        BookLoan.due_date < date.today()
    ).order_by(BookLoan.due_date.asc()).limit(5).all()

    # Recalculate fines for overdue preview
    for loan in overdue_loans:
        FineService.refresh_loan_fine(loan)

    return render_template(
        'librarian/dashboard.html',
        metrics=metrics,
        pending_requests=pending_requests,
        overdue_loans=overdue_loans,
        today=date.today()
    )


@librarian_bp.route('/requests')
@staff_required
def requests_list():
    """Manage all student borrow requests."""
    status_filter = request.args.get('status', 'Pending')
    query = BookRequest.query

    if status_filter != 'All':
        query = query.filter_by(status=status_filter)

    requests = query.order_by(BookRequest.requested_at.desc()).all()
    return render_template('librarian/requests.html', requests=requests, current_status=status_filter)


@librarian_bp.route('/requests/<int:request_id>/approve', methods=['POST'])
@staff_required
def approve_request(request_id):
    """Approve a student request and create an active loan."""
    success, message = CirculationService.approve_request(current_user, request_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(request.referrer or url_for('librarian.requests_list'))


@librarian_bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@staff_required
def reject_request(request_id):
    """Reject a student borrow request."""
    remarks = request.form.get('remarks', 'Rejected by librarian')
    success, message = CirculationService.reject_request(current_user, request_id, remarks)
    if success:
        flash(message, 'info')
    else:
        flash(message, 'danger')
    return redirect(request.referrer or url_for('librarian.requests_list'))


@librarian_bp.route('/loans')
@staff_required
def loans_list():
    """View and filter all library loans."""
    status_filter = request.args.get('status', 'Active')
    query = BookLoan.query

    if status_filter != 'All':
        query = query.filter_by(status=status_filter)

    loans = query.order_by(BookLoan.issue_date.desc()).all()
    return render_template('librarian/loans.html', loans=loans, current_status=status_filter, today=date.today())


@librarian_bp.route('/issue', methods=['GET', 'POST'])
@staff_required
def direct_issue():
    """Direct book issue to student without pre-existing request."""
    if request.method == 'POST':
        student_identifier = request.form.get('student_identifier', '').strip()
        book_id = request.form.get('book_id', type=int)
        days = request.form.get('borrow_days', type=int) or None

        # Look up student by student_id or email
        student = User.query.filter(
            (User.student_id == student_identifier.upper()) | (User.email == student_identifier.lower())
        ).first()

        if not student:
            flash(f"No student found with ID or Email '{student_identifier}'.", 'danger')
            return redirect(url_for('librarian.direct_issue'))

        if not student.is_student:
            flash("Books can only be issued to students.", 'warning')
            return redirect(url_for('librarian.direct_issue'))

        success, message = CirculationService.direct_issue(current_user, student.id, book_id, days)
        if success:
            flash(message, 'success')
            return redirect(url_for('librarian.loans_list'))
        else:
            flash(message, 'danger')

    available_books = Book.query.filter(Book.is_active == True, Book.available_copies > 0).order_by(Book.title.asc()).all()
    students = User.query.filter_by(role='student', is_active=True).order_by(User.full_name.asc()).all()
    return render_template('librarian/direct_issue.html', available_books=available_books, students=students)


@librarian_bp.route('/loans/<int:loan_id>/return', methods=['POST'])
@staff_required
def return_book(loan_id):
    """Record book return, increment available copies, and compute fines."""
    success, message = CirculationService.return_book(current_user, loan_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(request.referrer or url_for('librarian.loans_list'))


@librarian_bp.route('/overdue')
@staff_required
def overdue_list():
    """List of all overdue active loans with real-time fine calculation."""
    overdue_loans = BookLoan.query.filter(
        BookLoan.status == BookLoan.STATUS_ACTIVE,
        BookLoan.due_date < date.today()
    ).order_by(BookLoan.due_date.asc()).all()

    for loan in overdue_loans:
        FineService.refresh_loan_fine(loan)
    db.session.commit()

    return render_template('librarian/overdue.html', loans=overdue_loans, today=date.today())


@librarian_bp.route('/fines')
@staff_required
def fines_list():
    """List of all assessed fines and payment processing."""
    status_filter = request.args.get('status', 'Unpaid')
    query = Fine.query.join(BookLoan)

    if status_filter == 'Unpaid':
        query = query.filter(Fine.payment_status.in_([Fine.STATUS_PENDING, Fine.STATUS_PARTIALLY_PAID]))
    elif status_filter == 'Paid':
        query = query.filter(Fine.payment_status == Fine.STATUS_PAID)
    elif status_filter == 'Waived':
        query = query.filter(Fine.payment_status == Fine.STATUS_WAIVED)

    fines = query.order_by(Fine.updated_at.desc()).all()
    return render_template('librarian/fines.html', fines=fines, current_status=status_filter)


@librarian_bp.route('/fines/<int:fine_id>/pay', methods=['POST'])
@staff_required
def record_payment(fine_id):
    """Record fine payment receipt."""
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
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(request.referrer or url_for('librarian.fines_list'))


# ==========================================
# STUDENT ID CARD MANAGEMENT & DIRECT ISSUANCE
# ==========================================

@librarian_bp.route('/id-cards')
@staff_required
def id_cards_list():
    """List student ID card applications with status filtering, payment tracking, and actions."""
    status_filter = request.args.get('status', 'All')
    payment_filter = request.args.get('payment', 'All')
    role_filter = request.args.get('role_type', 'All')
    search_query = request.args.get('q', '').strip()

    query = StudentIdCard.query.join(User, StudentIdCard.student_id == User.id)

    if status_filter in ('Pending', 'Approved', 'Rejected'):
        query = query.filter(StudentIdCard.status == status_filter)
    if payment_filter in ('Pending', 'Paid', 'Waived'):
        query = query.filter(StudentIdCard.payment_status == payment_filter)
    if role_filter == 'Students':
        query = query.filter(User.role == 'student')
    elif role_filter == 'Staff':
        query = query.filter(User.role.in_(['librarian', 'admin']))

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
    staff_count = StudentIdCard.query.join(User, StudentIdCard.student_id == User.id).filter(User.role.in_(['librarian', 'admin'])).count()
    total_fees_collected = db.session.query(db.func.sum(StudentIdCard.fee_amount)).filter(
        StudentIdCard.payment_status.in_([StudentIdCard.PAYMENT_PAID, StudentIdCard.PAYMENT_WAIVED])
    ).scalar() or Decimal('0.00')

    return render_template(
        'librarian/id_cards.html',
        cards=cards,
        current_status=status_filter,
        current_payment=payment_filter,
        current_role=role_filter,
        search_query=search_query,
        total_count=total_count,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        staff_count=staff_count,
        total_fees_collected=total_fees_collected
    )


@librarian_bp.route('/id-cards/new', methods=['GET', 'POST'])
@staff_required
def id_card_create():
    """Directly issue/generate a Student ID Card by staff for a student."""
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
            return render_template('librarian/id_card_form.html', students=students)

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Handle photo upload or use profile image
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

        # Check if student already has a pending card; if so, update it
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
            card.payment_reference = payment_reference or ('DIRECT-STAFF-ISSUE' if payment_status != StudentIdCard.PAYMENT_PENDING else None)
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
                payment_reference=payment_reference or ('DIRECT-STAFF-ISSUE' if payment_status != StudentIdCard.PAYMENT_PENDING else None),
                paid_at=datetime.utcnow() if payment_status in (StudentIdCard.PAYMENT_PAID, StudentIdCard.PAYMENT_WAIVED) else None
            )
            db.session.add(card)
            db.session.flush()

        # Approve and set issue & expiry dates
        card.approve(staff_user_id=current_user.id, validity_years=validity_years)

        # Generate QR code for ID card
        QRService.generate_id_card_qr(card)

        AuditLog.record(
            actor_id=current_user.id,
            action='DIRECT_ISSUE_ID_CARD',
            entity_type='StudentIdCard',
            entity_id=card.id,
            details=f"Staff {current_user.email} directly generated and approved Student ID card {card.card_number} for {student.email}."
        )
        db.session.commit()

        flash(f"Student ID Card {card.card_number} created and approved successfully!", 'success')
        return redirect(url_for('librarian.id_card_view', card_id=card.id))

    return render_template('librarian/id_card_form.html', students=students)


@librarian_bp.route('/id-cards/<int:card_id>/approve', methods=['POST'])
@staff_required
def id_card_approve(card_id):
    """Approve a pending student ID card application."""
    card = StudentIdCard.query.get_or_404(card_id)

    # Rule: Staff & Librarian ID cards can only be approved by an Admin
    if card.student.is_staff and not current_user.is_admin:
        flash('Access Denied: Staff and Librarian ID cards can ONLY be approved by a System Administrator.', 'danger')
        return redirect(request.referrer or url_for('librarian.id_cards_list'))

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
        details=f"Staff {current_user.email} approved ID card {card.card_number} for {card.student.email}."
    )
    db.session.commit()

    flash(f"ID Card {card.card_number} approved and issued successfully!", 'success')
    return redirect(request.referrer or url_for('librarian.id_cards_list'))


@librarian_bp.route('/id-cards/<int:card_id>/reject', methods=['POST'])
@staff_required
def id_card_reject(card_id):
    """Reject a pending student ID card application with feedback."""
    card = StudentIdCard.query.get_or_404(card_id)

    # Rule: Staff & Librarian ID cards can only be rejected by an Admin
    if card.student.is_staff and not current_user.is_admin:
        flash('Access Denied: Staff and Librarian ID cards can ONLY be rejected by a System Administrator.', 'danger')
        return redirect(request.referrer or url_for('librarian.id_cards_list'))

    remarks = request.form.get('rejection_remarks', '').strip()
    if not remarks:
        remarks = 'Information provided could not be verified or photo is unclear. Please update and re-submit.'

    card.reject(staff_user_id=current_user.id, remarks=remarks)

    AuditLog.record(
        actor_id=current_user.id,
        action='REJECT_ID_CARD',
        entity_type='StudentIdCard',
        entity_id=card.id,
        details=f"Staff {current_user.email} rejected ID card application {card.card_number}. Remarks: {remarks}"
    )
    db.session.commit()

    flash(f"ID Card application {card.card_number} was rejected.", 'warning')
    return redirect(request.referrer or url_for('librarian.id_cards_list'))


@librarian_bp.route('/id-cards/<int:card_id>/view')
@staff_required
def id_card_view(card_id):
    """View detailed CR80 digital ID card and applicant verification details."""
    card = StudentIdCard.query.get_or_404(card_id)
    if card.is_approved and not card.qr_code_path:
        QRService.generate_id_card_qr(card)
        db.session.commit()
    return render_template('librarian/id_card_view.html', card=card)


@librarian_bp.route('/id-cards/<int:card_id>/print')
@staff_required
def id_card_print(card_id):
    """Staff printable view for a student ID card."""
    card = StudentIdCard.query.get_or_404(card_id)
    if not card.qr_code_path:
        QRService.generate_id_card_qr(card)
        db.session.commit()
    return render_template('student/id_card_print.html', card=card)


@librarian_bp.route('/my-id-card', methods=['GET', 'POST'])
@staff_required
def my_id_card():
    """Librarian request and view their own official Staff Library ID Card."""
    existing_card = StudentIdCard.query.filter_by(student_id=current_user.id).order_by(StudentIdCard.id.desc()).first()

    if request.method == 'POST':
        designation = request.form.get('designation', 'Librarian').strip()
        department = request.form.get('department', 'Central Library').strip()
        staff_code = request.form.get('staff_code', '').strip() or current_user.student_id or f"LIB{current_user.id:04d}"
        blood_group = request.form.get('blood_group', '').strip()
        dob_str = request.form.get('dob', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()
        address = request.form.get('address', '').strip()

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        photo_file = request.files.get('id_photo')
        photo_path = current_user.profile_image

        if photo_file and photo_file.filename:
            raw_ext = Path(photo_file.filename).suffix.lower()
            if raw_ext in ('.png', '.jpg', '.jpeg', '.webp'):
                clean_name = f"staffphoto_{current_user.id}_{uuid.uuid4().hex[:8]}{raw_ext}"
                avatars_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'avatars'
                avatars_dir.mkdir(parents=True, exist_ok=True)
                dest = avatars_dir / clean_name
                photo_file.save(str(dest))
                photo_path = f"uploads/avatars/{clean_name}"
                if not current_user.profile_image:
                    current_user.profile_image = photo_path

        card_number = StudentIdCard.generate_card_number(staff_code)

        if existing_card and existing_card.status == StudentIdCard.STATUS_REJECTED:
            card = existing_card
            card.roll_number = staff_code
            card.course_branch = department
            card.academic_year = designation
            card.blood_group = blood_group
            card.dob = dob
            card.emergency_contact = emergency_contact
            card.address = address
            if photo_path:
                card.photo_path = photo_path
            card.status = StudentIdCard.STATUS_PENDING
            card.rejection_remarks = None
        else:
            card = StudentIdCard(
                student_id=current_user.id,
                roll_number=staff_code,
                course_branch=department,
                academic_year=designation,
                blood_group=blood_group,
                dob=dob,
                emergency_contact=emergency_contact,
                address=address,
                photo_path=photo_path,
                card_number=card_number,
                fee_amount=Decimal('0.00'),
                payment_status=StudentIdCard.PAYMENT_WAIVED,
                payment_method='Staff / Institutional',
                status=StudentIdCard.STATUS_PENDING
            )
            db.session.add(card)

        AuditLog.record(
            actor_id=current_user.id,
            action='REQUEST_STAFF_ID_CARD',
            entity_type='StudentIdCard',
            entity_id=card.id,
            details=f"Librarian {current_user.email} submitted Staff ID card request ({card.card_number})."
        )
        db.session.commit()

        flash('Staff Library ID Card application submitted! As per library policy, it is queued for Administrator approval.', 'info')
        return redirect(url_for('librarian.my_id_card'))

    if existing_card and existing_card.is_approved and not existing_card.qr_code_path:
        QRService.generate_id_card_qr(existing_card)
        db.session.commit()

    return render_template('librarian/my_id_card.html', card=existing_card, role_title='Librarian')
