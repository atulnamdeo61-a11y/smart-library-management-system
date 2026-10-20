import pytest
from app.extensions import db
from app.models.book import Book
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.services.circulation_service import CirculationService


def test_student_submit_borrow_request(app, seed_test_data):
    """Test valid borrow request submission."""
    with app.app_context():
        student = seed_test_data['student1']
        book = seed_test_data['book1']

        success, msg = CirculationService.request_book(student, book.id)
        assert success is True
        assert "submitted successfully" in msg

        req = BookRequest.query.filter_by(student_id=student.id, book_id=book.id).first()
        assert req is not None
        assert req.status == BookRequest.STATUS_PENDING


def test_unavailable_book_cannot_be_requested(app, seed_test_data):
    """Cannot request book with 0 available copies."""
    with app.app_context():
        student = seed_test_data['student1']
        unavail_book = seed_test_data['book_unavailable']

        success, msg = CirculationService.request_book(student, unavail_book.id)
        assert success is False
        assert "No copies" in msg


def test_duplicate_pending_request_rejected(app, seed_test_data):
    """Duplicate pending request for same book must be rejected."""
    with app.app_context():
        student = seed_test_data['student1']
        book = seed_test_data['book1']

        # First request
        success, _ = CirculationService.request_book(student, book.id)
        assert success is True

        # Second request
        dup_success, dup_msg = CirculationService.request_book(student, book.id)
        assert dup_success is False
        assert "already have a pending borrow request" in dup_msg


def test_approval_workflow_creates_loan_and_updates_stock(app, seed_test_data):
    """Approving request decrements available_copies and generates an active BookLoan."""
    with app.app_context():
        student = seed_test_data['student1']
        staff = seed_test_data['librarian']
        book = seed_test_data['book1']
        initial_avail = book.available_copies

        # 1. Request
        CirculationService.request_book(student, book.id)
        req = BookRequest.query.filter_by(student_id=student.id, book_id=book.id, status=BookRequest.STATUS_PENDING).first()

        # 2. Approve
        success, msg = CirculationService.approve_request(staff, req.id)
        assert success is True

        # 3. Verify stock decremented
        updated_book = db.session.get(Book, book.id)
        assert updated_book.available_copies == initial_avail - 1

        # 4. Verify loan created
        loan = BookLoan.query.filter_by(student_id=student.id, book_id=book.id, status=BookLoan.STATUS_ACTIVE).first()
        assert loan is not None
        assert loan.fine is not None
        assert loan.due_date > loan.issue_date


def test_return_book_updates_stock_once_and_rejects_duplicate(app, seed_test_data):
    """Returning book increments available copies and rejects double returns."""
    with app.app_context():
        student = seed_test_data['student1']
        staff = seed_test_data['librarian']
        book = seed_test_data['book2']
        initial_avail = book.available_copies

        # Issue book directly
        success, _ = CirculationService.direct_issue(staff, student.id, book.id)
        assert success is True
        b_after_issue = db.session.get(Book, book.id)
        assert b_after_issue.available_copies == initial_avail - 1

        loan = BookLoan.query.filter_by(student_id=student.id, book_id=book.id, status=BookLoan.STATUS_ACTIVE).first()

        # 1. Return book
        ret_success, ret_msg = CirculationService.return_book(staff, loan.id)
        assert ret_success is True
        b_after_return = db.session.get(Book, book.id)
        assert b_after_return.available_copies == initial_avail

        # 2. Attempt duplicate return on same loan
        dup_ret_success, dup_ret_msg = CirculationService.return_book(staff, loan.id)
        assert dup_ret_success is False
        assert "already been marked as returned" in dup_ret_msg

        # Stock must NOT increment again
        b_after_dup = db.session.get(Book, book.id)
        assert b_after_dup.available_copies == initial_avail
