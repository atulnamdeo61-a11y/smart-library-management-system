from datetime import date, timedelta
from decimal import Decimal
import pytest
from app.extensions import db
from app.models.book_loan import BookLoan
from app.models.fine import Fine
from app.services.fine_service import calculate_fine_for_loan, FineService


def test_no_fine_charged_before_due_date(app, seed_test_data):
    """Loans within due date accrue zero fine."""
    with app.app_context():
        loan = BookLoan(
            student_id=seed_test_data['student1'].id,
            book_id=seed_test_data['book1'].id,
            issued_by=seed_test_data['librarian'].id,
            issue_date=date.today() - timedelta(days=5),
            due_date=date.today() + timedelta(days=9),  # 9 days in future
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        fine_amount, overdue_days = calculate_fine_for_loan(loan)
        assert fine_amount == Decimal('0.00')
        assert overdue_days == 0


def test_overdue_fine_calculated_accurately(app, seed_test_data):
    """Overdue loans accrue ₹2.00 per overdue day."""
    with app.app_context():
        loan = BookLoan(
            student_id=seed_test_data['student1'].id,
            book_id=seed_test_data['book1'].id,
            issued_by=seed_test_data['librarian'].id,
            issue_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=5),  # 5 days overdue
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        # 5 days * ₹2 = ₹10.00
        fine_amount, overdue_days = calculate_fine_for_loan(loan)
        assert fine_amount == Decimal('10.00')
        assert overdue_days == 5


def test_returned_loan_freezes_fine_accrual(app, seed_test_data):
    """Once returned, fine is based on actual return date, not today's date."""
    with app.app_context():
        loan = BookLoan(
            student_id=seed_test_data['student1'].id,
            book_id=seed_test_data['book1'].id,
            issued_by=seed_test_data['librarian'].id,
            issue_date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=16),
            return_date=date.today() - timedelta(days=13),  # returned 3 days overdue 13 days ago
            status=BookLoan.STATUS_RETURNED,
            fine_rate_snapshot=2.00
        )
        # 3 overdue days * ₹2 = ₹6.00 (not 16 days!)
        fine_amount, overdue_days = calculate_fine_for_loan(loan)
        assert fine_amount == Decimal('6.00')
        assert overdue_days == 3


def test_fine_payment_validation_and_settlement(app, seed_test_data):
    """Test payment validation: reject overpayments, accept valid payment, update status."""
    with app.app_context():
        student = seed_test_data['student1']
        staff = seed_test_data['librarian']
        book = seed_test_data['book1']

        loan = BookLoan(
            student_id=student.id,
            book_id=book.id,
            issued_by=staff.id,
            issue_date=date.today() - timedelta(days=10),
            due_date=date.today() - timedelta(days=4),  # 4 days overdue
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        db.session.add(loan)
        db.session.flush()

        fine = Fine(loan_id=loan.id, calculated_amount=Decimal('8.00'), amount_paid=Decimal('0.00'))
        fine.update_payment_status()
        db.session.add(fine)
        db.session.commit()

        # 1. Negative payment rejected
        neg_success, _ = FineService.record_payment(fine.id, staff, -5.00)
        assert neg_success is False

        # 2. Overpayment rejected
        over_success, _ = FineService.record_payment(fine.id, staff, 15.00)
        assert over_success is False

        # 3. Partial payment of ₹5.00
        p_success, _ = FineService.record_payment(fine.id, staff, 5.00, payment_method='Cash')
        assert p_success is True
        db.session.refresh(fine)
        assert fine.amount_paid == Decimal('5.00')
        assert fine.outstanding_amount == Decimal('3.00')
        assert fine.payment_status == Fine.STATUS_PARTIALLY_PAID

        # 4. Final payment of remaining ₹3.00
        f_success, _ = FineService.record_payment(fine.id, staff, 3.00, payment_method='Cash')
        assert f_success is True
        db.session.refresh(fine)
        assert fine.amount_paid == Decimal('8.00')
        assert fine.outstanding_amount == Decimal('0.00')
        assert fine.payment_status == Fine.STATUS_PAID


def test_fines_view_filter_by_status(app, client, seed_test_data):
    """Verify that filtering fines by Paid, Unpaid, Waived, and All returns HTTP 200 without SQL errors."""
    with app.app_context():
        student = seed_test_data['student1']
        staff = seed_test_data['librarian']
        book = seed_test_data['book1']

        loan = BookLoan(
            student_id=student.id,
            book_id=book.id,
            issued_by=staff.id,
            issue_date=date.today() - timedelta(days=10),
            due_date=date.today() - timedelta(days=2),
            status=BookLoan.STATUS_ACTIVE,
            fine_rate_snapshot=2.00
        )
        db.session.add(loan)
        db.session.flush()

        fine = Fine(loan_id=loan.id, calculated_amount=Decimal('10.00'), amount_paid=Decimal('10.00'), payment_status=Fine.STATUS_PAID)
        db.session.add(fine)
        db.session.commit()

    # Login as Librarian
    client.post('/auth/login', data={'email': 'librarian@test.edu', 'password': 'LibPass123'}, follow_redirects=True)

    for status in ['Paid', 'Unpaid', 'Waived', 'All']:
        res = client.get(f'/librarian/fines?status={status}')
        assert res.status_code == 200, f"Librarian fines route failed with status={status}"
        assert b"Fine Records" in res.data

    # Logout librarian and login as Admin
    client.get('/auth/logout', follow_redirects=True)
    client.post('/auth/login', data={'email': 'admin@test.edu', 'password': 'AdminPass123'}, follow_redirects=True)

    for status in ['Paid', 'Unpaid', 'Waived', 'All']:
        res = client.get(f'/admin/fines?status={status}')
        assert res.status_code == 200, f"Admin fines route failed with status={status}"
        assert b"Fine Administration" in res.data

