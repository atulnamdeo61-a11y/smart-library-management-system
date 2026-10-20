from datetime import datetime, date, timedelta
from flask import current_app
from app.extensions import db
from app.models.book import Book
from app.models.book_request import BookRequest
from app.models.book_loan import BookLoan
from app.models.fine import Fine
from app.models.audit_log import AuditLog
from app.services.fine_service import calculate_fine_for_loan


class CirculationService:
    @staticmethod
    def get_max_loans():
        return current_app.config.get('MAX_ACTIVE_LOANS_PER_STUDENT', 3)

    @staticmethod
    def get_default_borrow_days():
        return current_app.config.get('DEFAULT_BORROW_DAYS', 14)

    @classmethod
    def can_student_borrow(cls, student_id):
        """Check if student is eligible to borrow another book."""
        active_loans_count = BookLoan.query.filter_by(
            student_id=student_id,
            status=BookLoan.STATUS_ACTIVE
        ).count()
        return active_loans_count < cls.get_max_loans(), active_loans_count, cls.get_max_loans()

    @classmethod
    def request_book(cls, student, book_id):
        """Student requests to borrow a book."""
        book = db.session.get(Book, book_id)
        if not book or not book.is_active:
            return False, "Book is not available in the catalog."

        if book.available_copies <= 0:
            return False, "No copies of this book are currently available for borrowing."

        can_borrow, active_count, max_limit = cls.can_student_borrow(student.id)
        if not can_borrow:
            return False, f"Borrowing limit reached: You have {active_count} active loans (maximum allowed is {max_limit})."

        # Check for existing pending request for same book
        existing_request = BookRequest.query.filter_by(
            student_id=student.id,
            book_id=book.id,
            status=BookRequest.STATUS_PENDING
        ).first()
        if existing_request:
            return False, "You already have a pending borrow request for this book."

        # Check if student already currently has an active loan of this book
        existing_loan = BookLoan.query.filter_by(
            student_id=student.id,
            book_id=book.id,
            status=BookLoan.STATUS_ACTIVE
        ).first()
        if existing_loan:
            return False, "You already currently have an active borrowed copy of this book."

        try:
            req = BookRequest(
                student_id=student.id,
                book_id=book.id,
                status=BookRequest.STATUS_PENDING
            )
            db.session.add(req)
            AuditLog.record(
                actor_id=student.id,
                action='REQUEST_BOOK',
                entity_type='BookRequest',
                entity_id=None,
                details=f"Student requested book '{book.title}' (ISBN: {book.isbn})"
            )
            db.session.commit()
            return True, "Borrow request submitted successfully. Awaiting librarian approval."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to submit request: {str(e)}"

    @classmethod
    def cancel_request(cls, student, request_id):
        """Student cancels their pending borrow request."""
        req = db.session.get(BookRequest, request_id)
        if not req or req.student_id != student.id:
            return False, "Request not found."

        if req.status != BookRequest.STATUS_PENDING:
            return False, f"Cannot cancel a request that has already been {req.status.lower()}."

        try:
            req.status = BookRequest.STATUS_CANCELLED
            AuditLog.record(
                actor_id=student.id,
                action='CANCEL_REQUEST',
                entity_type='BookRequest',
                entity_id=req.id,
                details="Student cancelled pending borrow request."
            )
            db.session.commit()
            return True, "Borrow request cancelled successfully."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to cancel request: {str(e)}"

    @classmethod
    def approve_request(cls, staff_user, request_id):
        """
        Librarian/Admin approves a pending borrow request.
        Converts the request into an active BookLoan and decrements available copies safely.
        """
        req = db.session.get(BookRequest, request_id)
        if not req:
            return False, "Request not found."

        if req.status != BookRequest.STATUS_PENDING:
            return False, f"Request has already been processed (Status: {req.status})."

        book = Book.query.get(req.book_id)
        if not book or not book.is_active:
            return False, "Requested book is no longer active."

        if book.available_copies <= 0:
            return False, "Cannot approve: No physical copies are currently available."

        can_borrow, active_count, max_limit = cls.can_student_borrow(req.student_id)
        if not can_borrow:
            return False, f"Cannot approve: Student currently has {active_count} active loans (limit {max_limit})."

        try:
            # 1. Update request status
            req.status = BookRequest.STATUS_APPROVED
            req.reviewed_by = staff_user.id
            req.reviewed_at = datetime.utcnow()

            # 2. Decrement available copies safely
            book.available_copies -= 1

            # 3. Create active loan
            fine_rate = current_app.config.get('FINE_RATE_PER_DAY', 2.00)
            borrow_days = cls.get_default_borrow_days()
            issue_d = date.today()
            due_d = issue_d + timedelta(days=borrow_days)

            loan = BookLoan(
                student_id=req.student_id,
                book_id=book.id,
                issued_by=staff_user.id,
                issue_date=issue_d,
                due_date=due_d,
                status=BookLoan.STATUS_ACTIVE,
                fine_rate_snapshot=fine_rate
            )
            db.session.add(loan)
            db.session.flush()  # populate loan.id

            # 4. Initialize fine record
            fine = Fine(
                loan_id=loan.id,
                calculated_amount=0.00,
                amount_paid=0.00,
                payment_status=Fine.STATUS_NO_FINE
            )
            db.session.add(fine)

            AuditLog.record(
                actor_id=staff_user.id,
                action='APPROVE_REQUEST',
                entity_type='BookLoan',
                entity_id=loan.id,
                details=f"Approved request #{req.id} for book '{book.title}' to student #{req.student_id}. Due date: {due_d}"
            )
            db.session.commit()
            return True, f"Request approved. Book issued successfully! Due date is {due_d.strftime('%d-%b-%Y')}."
        except Exception as e:
            db.session.rollback()
            return False, f"Approval transaction failed: {str(e)}"

    @classmethod
    def reject_request(cls, staff_user, request_id, remarks="Request rejected by library staff"):
        """Librarian/Admin rejects a borrow request."""
        req = db.session.get(BookRequest, request_id)
        if not req:
            return False, "Request not found."

        if req.status != BookRequest.STATUS_PENDING:
            return False, f"Request has already been processed (Status: {req.status})."

        try:
            req.status = BookRequest.STATUS_REJECTED
            req.reviewed_by = staff_user.id
            req.reviewed_at = datetime.utcnow()
            req.remarks = remarks

            AuditLog.record(
                actor_id=staff_user.id,
                action='REJECT_REQUEST',
                entity_type='BookRequest',
                entity_id=req.id,
                details=f"Rejected request #{req.id}. Remarks: {remarks}"
            )
            db.session.commit()
            return True, "Request has been rejected."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to reject request: {str(e)}"

    @classmethod
    def direct_issue(cls, staff_user, student_id, book_id, days=None):
        """Staff issues a book directly without pre-existing request."""
        book = db.session.get(Book, book_id)
        if not book or not book.is_active:
            return False, "Book not found or inactive."

        if book.available_copies <= 0:
            return False, "Cannot issue: No copies currently available."

        can_borrow, active_count, max_limit = cls.can_student_borrow(student_id)
        if not can_borrow:
            return False, f"Student already has {active_count} active loans (limit is {max_limit})."

        # Check existing loan
        existing = BookLoan.query.filter_by(
            student_id=student_id,
            book_id=book_id,
            status=BookLoan.STATUS_ACTIVE
        ).first()
        if existing:
            return False, "Student already has an active loan for this book."

        try:
            borrow_days = days or cls.get_default_borrow_days()
            fine_rate = current_app.config.get('FINE_RATE_PER_DAY', 2.00)
            issue_d = date.today()
            due_d = issue_d + timedelta(days=borrow_days)

            book.available_copies -= 1

            loan = BookLoan(
                student_id=student_id,
                book_id=book.id,
                issued_by=staff_user.id,
                issue_date=issue_d,
                due_date=due_d,
                status=BookLoan.STATUS_ACTIVE,
                fine_rate_snapshot=fine_rate
            )
            db.session.add(loan)
            db.session.flush()

            fine = Fine(
                loan_id=loan.id,
                calculated_amount=0.00,
                amount_paid=0.00,
                payment_status=Fine.STATUS_NO_FINE
            )
            db.session.add(fine)

            AuditLog.record(
                actor_id=staff_user.id,
                action='DIRECT_ISSUE',
                entity_type='BookLoan',
                entity_id=loan.id,
                details=f"Issued book '{book.title}' directly to student #{student_id}. Due: {due_d}"
            )
            db.session.commit()
            return True, f"Book issued successfully! Due date: {due_d.strftime('%d-%b-%Y')}."
        except Exception as e:
            db.session.rollback()
            return False, f"Direct issue failed: {str(e)}"

    @classmethod
    def return_book(cls, staff_user, loan_id):
        """
        Staff records the return of a borrowed book.
        Calculates overdue fine, marks loan Returned, and increments available copies.
        """
        loan = db.session.get(BookLoan, loan_id)
        if not loan:
            return False, "Loan record not found."

        if loan.status != BookLoan.STATUS_ACTIVE:
            return False, "This book loan has already been marked as returned."

        book = db.session.get(Book, loan.book_id)
        if not book:
            return False, "Associated book record not found."

        try:
            return_d = date.today()
            loan.return_date = return_d
            loan.status = BookLoan.STATUS_RETURNED

            # Prevent available_copies from exceeding total_copies
            if book.available_copies < book.total_copies:
                book.available_copies += 1

            # Calculate and finalize fine
            fine_amount, overdue_days = calculate_fine_for_loan(loan)
            fine = loan.fine
            if not fine:
                fine = Fine(loan_id=loan.id)
                db.session.add(fine)

            fine.calculated_amount = fine_amount
            fine.last_calculated_at = datetime.utcnow()
            fine.update_payment_status()

            msg_fine = f" Overdue fine: ₹{fine_amount:.2f} ({overdue_days} days overdue)." if fine_amount > 0 else " No overdue fine."

            AuditLog.record(
                actor_id=staff_user.id,
                action='RETURN_BOOK',
                entity_type='BookLoan',
                entity_id=loan.id,
                details=f"Book '{book.title}' returned by student #{loan.student_id}.{msg_fine}"
            )
            db.session.commit()
            return True, f"Book returned successfully.{msg_fine}"
        except Exception as e:
            db.session.rollback()
            return False, f"Return operation failed: {str(e)}"
