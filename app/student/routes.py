import uuid
from pathlib import Path
from decimal import Decimal
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.auth.decorators import student_required
from app.models.book_loan import BookLoan
from app.models.book_request import BookRequest
from app.models.fine import Fine
from app.models.category import Category
from app.models.student_preference import StudentPreference
from app.models.audit_log import AuditLog
from app.models.id_card import StudentIdCard
from app.services.circulation_service import CirculationService
from app.services.recommendation_service import RecommendationService
from app.services.fine_service import FineService
from app.services.qr_service import QRService

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@student_required
def dashboard():
    """Student central dashboard with active loans, smart overdue alerts, requests, and recommendations."""
    # Active loans
    active_loans = BookLoan.query.filter_by(
        student_id=current_user.id,
        status=BookLoan.STATUS_ACTIVE
    ).order_by(BookLoan.due_date.asc()).all()

    # Smart overdue alerts
    overdue_alerts = []
    for loan in active_loans:
        if loan.is_overdue:
            fine_amount, days = loan.fine.calculated_amount if loan.fine else (0, 0), loan.overdue_days
            overdue_alerts.append({
                'loan': loan,
                'days': days,
                'fine': FineService.format_currency(loan.fine.calculated_amount if loan.fine else 0)
            })

    # Pending requests
    pending_requests = BookRequest.query.filter_by(
        student_id=current_user.id,
        status=BookRequest.STATUS_PENDING
    ).order_by(BookRequest.requested_at.desc()).all()

    # Recommendations
    recommendations = RecommendationService.get_recommendations_for_student(current_user.id, limit=4)

    # Outstanding fines
    outstanding_fines = [
        loan.fine for loan in BookLoan.query.filter_by(student_id=current_user.id).all()
        if loan.fine and loan.fine.outstanding_amount > 0
    ]
    total_unpaid = sum((f.outstanding_amount for f in outstanding_fines), 0)

    can_borrow, active_count, max_limit = CirculationService.can_student_borrow(current_user.id)

    return render_template(
        'student/dashboard.html',
        active_loans=active_loans,
        overdue_alerts=overdue_alerts,
        pending_requests=pending_requests,
        recommendations=recommendations,
        total_unpaid_fines=FineService.format_currency(total_unpaid),
        active_count=active_count,
        max_limit=max_limit,
        today=date.today()
    )


@student_bp.route('/loans')
@student_required
def loans():
    """Detailed view of currently active loans with due date countdown."""
    active_loans = BookLoan.query.filter_by(
        student_id=current_user.id,
        status=BookLoan.STATUS_ACTIVE
    ).order_by(BookLoan.due_date.asc()).all()

    return render_template('student/loans.html', loans=active_loans, today=date.today())


@student_bp.route('/history')
@student_required
def history():
    """Historical record of all returned books."""
    returned_loans = BookLoan.query.filter_by(
        student_id=current_user.id,
        status=BookLoan.STATUS_RETURNED
    ).order_by(BookLoan.return_date.desc()).all()

    all_requests = BookRequest.query.filter_by(
        student_id=current_user.id
    ).order_by(BookRequest.requested_at.desc()).all()

    return render_template('student/history.html', returned_loans=returned_loans, requests=all_requests)


@student_bp.route('/fines')
@student_required
def fines():
    """View of fines, payments, and outstanding balances."""
    loans_with_fines = BookLoan.query.filter_by(student_id=current_user.id).join(Fine).all()

    total_assessed = sum((l.fine.calculated_amount for l in loans_with_fines if l.fine), 0)
    total_paid = sum((l.fine.amount_paid for l in loans_with_fines if l.fine), 0)
    total_outstanding = sum((l.fine.outstanding_amount for l in loans_with_fines if l.fine), 0)

    return render_template(
        'student/fines.html',
        loans_with_fines=loans_with_fines,
        total_assessed=FineService.format_currency(total_assessed),
        total_paid=FineService.format_currency(total_paid),
        total_outstanding=FineService.format_currency(total_outstanding)
    )


@student_bp.route('/recommendations')
@student_required
def recommendations():
    """Personalized recommendations page based on history and category preferences."""
    rec_list = RecommendationService.get_recommendations_for_student(current_user.id, limit=12)
    user_prefs = [p.category_id for p in current_user.preferences.all()]

    return render_template(
        'student/recommendations.html',
        recommendations=rec_list,
        has_preferences=bool(user_prefs)
    )


@student_bp.route('/preferences', methods=['GET', 'POST'])
@student_required
def preferences():
    """Manage student reading interests to tune the recommendation engine."""
    all_categories = Category.query.order_by(Category.name.asc()).all()

    if request.method == 'POST':
        selected_cat_ids = request.form.getlist('category_ids', type=int)

        try:
            # Clear previous preferences
            StudentPreference.query.filter_by(student_id=current_user.id).delete()

            for cat_id in selected_cat_ids:
                pref = StudentPreference(student_id=current_user.id, category_id=cat_id)
                db.session.add(pref)

            db.session.commit()
            flash('Your reading interests have been updated successfully! Check your recommendations.', 'success')
            return redirect(url_for('student.recommendations'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to update reading preferences. Please try again.', 'danger')

    current_pref_ids = {p.category_id for p in current_user.preferences.all()}
    return render_template('student/preferences.html', categories=all_categories, current_pref_ids=current_pref_ids)


@student_bp.route('/books/<int:book_id>/request', methods=['POST'])
@student_required
def request_book(book_id):
    """Action: Student submits a borrow request for a book."""
    success, message = CirculationService.request_book(current_user, book_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
    return redirect(url_for('books.detail', book_id=book_id))


@student_bp.route('/requests/<int:request_id>/cancel', methods=['POST'])
@student_required
def cancel_request(request_id):
    """Action: Student cancels their pending request."""
    success, message = CirculationService.cancel_request(current_user, request_id)
    if success:
        flash(message, 'info')
    else:
        flash(message, 'warning')
    return redirect(url_for('student.dashboard'))


@student_bp.route('/profile', methods=['GET', 'POST'])
@student_required
def profile():
    """Redirect to unified profile and security settings."""
    return redirect(url_for('auth.profile'))


@student_bp.route('/id-card', methods=['GET', 'POST'])
@student_required
def id_card():
    """Student ID Card application submission, dynamic UPI payment, and card display."""
    existing_card = StudentIdCard.query.filter_by(student_id=current_user.id).order_by(StudentIdCard.id.desc()).first()

    if request.method == 'POST':
        course_branch = request.form.get('course_branch', '').strip()
        academic_year = request.form.get('academic_year', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        dob_str = request.form.get('dob', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()
        address = request.form.get('address', '').strip()

        if not course_branch or not academic_year:
            flash('Course/Branch and Academic Year are mandatory fields.', 'danger')
            return redirect(url_for('student.id_card'))

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Handle photo: check if new photo uploaded, else fallback to user's profile image
        photo_file = request.files.get('id_photo')
        photo_path = current_user.profile_image

        if photo_file and photo_file.filename:
            raw_ext = Path(photo_file.filename).suffix.lower()
            if raw_ext in ('.png', '.jpg', '.jpeg', '.webp'):
                clean_name = f"idphoto_{current_user.id}_{uuid.uuid4().hex[:8]}{raw_ext}"
                avatars_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'avatars'
                avatars_dir.mkdir(parents=True, exist_ok=True)
                dest = avatars_dir / clean_name
                photo_file.save(str(dest))
                photo_path = f"uploads/avatars/{clean_name}"
                if not current_user.profile_image:
                    current_user.profile_image = photo_path

        card_number = StudentIdCard.generate_card_number(current_user.student_id or str(current_user.id))
        fee = Decimal(str(current_app.config.get('ID_CARD_FEE', 50.00)))
        upi_id = current_app.config.get('UPI_ID', 'smartlibrary@upi')
        payee_name = current_app.config.get('UPI_PAYEE_NAME', 'Smart College Library')

        if existing_card and existing_card.status == StudentIdCard.STATUS_REJECTED:
            card = existing_card
            card.course_branch = course_branch
            card.academic_year = academic_year
            card.blood_group = blood_group
            card.dob = dob
            card.emergency_contact = emergency_contact
            card.address = address
            if photo_path:
                card.photo_path = photo_path
            card.status = StudentIdCard.STATUS_PENDING
            card.payment_status = StudentIdCard.PAYMENT_PENDING
            card.payment_reference = None
            card.rejection_remarks = None
        else:
            card = StudentIdCard(
                student_id=current_user.id,
                roll_number=current_user.student_id or f"STU{current_user.id:04d}",
                course_branch=course_branch,
                academic_year=academic_year,
                blood_group=blood_group,
                dob=dob,
                emergency_contact=emergency_contact,
                address=address,
                photo_path=photo_path,
                card_number=card_number,
                fee_amount=fee,
                payment_status=StudentIdCard.PAYMENT_PENDING,
                status=StudentIdCard.STATUS_PENDING
            )
            db.session.add(card)
            db.session.flush()

        # Generate dynamic UPI Payment QR Code
        note = f"IDCard-{card.roll_number}-{card.id}"
        upi_qr_rel_path, _ = QRService.generate_upi_qr(
            upi_id=upi_id,
            payee_name=payee_name,
            amount=float(fee),
            note=note,
            reference_id=str(card.id)
        )
        card.upi_qr_path = upi_qr_rel_path

        AuditLog.record(
            actor_id=current_user.id,
            action='REQUEST_ID_CARD',
            entity_type='StudentIdCard',
            entity_id=card.id,
            details=f"Student {current_user.email} applied for ID card ({card.card_number})."
        )
        db.session.commit()

        flash('Your Student ID Card application was created! Please complete payment via UPI below to submit for librarian approval.', 'info')
        return redirect(url_for('student.id_card'))

    # Prepare UPI URI if payment is pending
    upi_uri = None
    if existing_card:
        if existing_card.is_approved and not existing_card.qr_code_path:
            QRService.generate_id_card_qr(existing_card)
            db.session.commit()
        elif not existing_card.is_paid:
            upi_id = current_app.config.get('UPI_ID', 'smartlibrary@upi')
            payee_name = current_app.config.get('UPI_PAYEE_NAME', 'Smart College Library')
            note = f"IDCard-{existing_card.roll_number}-{existing_card.id}"
            clean_amount = f"{float(existing_card.fee_amount):.2f}"
            upi_uri = f"upi://pay?pa={upi_id}&pn={payee_name}&am={clean_amount}&cu=INR&tn={note}"
            if not existing_card.upi_qr_path:
                qr_path, _ = QRService.generate_upi_qr(upi_id, payee_name, float(existing_card.fee_amount), note, str(existing_card.id))
                existing_card.upi_qr_path = qr_path
                db.session.commit()

    return render_template('student/id_card.html', card=existing_card, upi_uri=upi_uri)


@student_bp.route('/id-card/pay', methods=['POST'])
@student_required
def id_card_submit_payment():
    """Submit UPI transaction reference (UTR) for ID Card fee."""
    card = StudentIdCard.query.filter_by(student_id=current_user.id).order_by(StudentIdCard.id.desc()).first_or_404()
    utr_reference = request.form.get('utr_reference', '').strip()

    if not utr_reference or len(utr_reference) < 6:
        flash('Please enter a valid UPI Transaction Reference / UTR Number (minimum 6 digits).', 'danger')
        return redirect(url_for('student.id_card'))

    card.record_upi_payment(utr_reference)
    AuditLog.record(
        actor_id=current_user.id,
        action='ID_CARD_UPI_PAYMENT',
        entity_type='StudentIdCard',
        entity_id=card.id,
        details=f"Student {current_user.email} submitted UPI payment with UTR '{utr_reference}' for ID Card {card.card_number}."
    )
    db.session.commit()

    flash(f"Payment reference '{utr_reference}' recorded! Your application is now queued for librarian approval.", 'success')
    return redirect(url_for('student.id_card'))


@student_bp.route('/id-card/print')
@student_required
def id_card_print():
    """Printable digital copy of the approved student ID card."""
    card = StudentIdCard.query.filter_by(student_id=current_user.id, status=StudentIdCard.STATUS_APPROVED).first_or_404()
    if not card.qr_code_path:
        QRService.generate_id_card_qr(card)
        db.session.commit()
    return render_template('student/id_card_print.html', card=card)


