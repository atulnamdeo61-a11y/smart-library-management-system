from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models.book import Book
from app.models.category import Category
from app.models.user import User
from app.models.book_loan import BookLoan
from app.models.book_request import BookRequest
from app.models.fine import Fine, FinePayment
from app.services.fine_service import FineService


class AnalyticsService:
    @classmethod
    def get_dashboard_metrics(cls):
        """Aggregate high-level library key performance indicators from the database."""
        # Book counts
        total_unique_books = Book.query.filter_by(is_active=True).count()
        total_physical_copies = db.session.query(func.coalesce(func.sum(Book.total_copies), 0)).filter(Book.is_active == True).scalar()
        available_copies = db.session.query(func.coalesce(func.sum(Book.available_copies), 0)).filter(Book.is_active == True).scalar()
        borrowed_copies = max(0, total_physical_copies - available_copies)

        # Circulation counts
        active_loans = BookLoan.query.filter_by(status=BookLoan.STATUS_ACTIVE).count()
        overdue_loans = BookLoan.query.filter(
            BookLoan.status == BookLoan.STATUS_ACTIVE,
            BookLoan.due_date < date.today()
        ).count()
        pending_requests = BookRequest.query.filter_by(status=BookRequest.STATUS_PENDING).count()

        # User counts
        total_students = User.query.filter_by(role='student', is_active=True).count()
        total_librarians = User.query.filter_by(role='librarian', is_active=True).count()

        # Financial metrics
        total_fine_assessed = db.session.query(func.coalesce(func.sum(Fine.calculated_amount), Decimal('0.00'))).scalar()
        total_fine_paid = db.session.query(func.coalesce(func.sum(Fine.amount_paid), Decimal('0.00'))).scalar()
        total_outstanding_fines = db.session.query(
            func.coalesce(func.sum(Fine.calculated_amount - Fine.amount_paid), Decimal('0.00'))
        ).filter(
            Fine.payment_status.in_([Fine.STATUS_PENDING, Fine.STATUS_PARTIALLY_PAID])
        ).scalar()

        return {
            'total_unique_books': total_unique_books,
            'total_physical_copies': int(total_physical_copies or 0),
            'available_copies': int(available_copies or 0),
            'borrowed_copies': int(borrowed_copies or 0),
            'active_loans': active_loans,
            'overdue_loans': overdue_loans,
            'pending_requests': pending_requests,
            'total_students': total_students,
            'total_librarians': total_librarians,
            'total_fine_assessed': float(total_fine_assessed or 0),
            'total_fine_paid': float(total_fine_paid or 0),
            'total_outstanding_fines': float(total_outstanding_fines or 0),
            'formatted_outstanding_fines': FineService.format_currency(total_outstanding_fines or 0),
            'formatted_total_paid': FineService.format_currency(total_fine_paid or 0),
        }

    @classmethod
    def get_chart_data(cls):
        """Build structured Chart.js datasets from actual database queries."""
        # 1. Books by category
        cat_data = db.session.query(
            Category.name,
            func.count(Book.id)
        ).join(Book, Book.category_id == Category.id).filter(
            Book.is_active == True
        ).group_by(Category.name).all()

        category_labels = [row[0] for row in cat_data]
        category_counts = [row[1] for row in cat_data]

        if not category_labels:
            category_labels = ['No Categories']
            category_counts = [0]

        # 2. Monthly borrowing activity (last 6 months)
        today = date.today()
        month_labels = []
        month_counts = []

        for i in range(5, -1, -1):
            # calculate year and month
            m_target = (today.month - i - 1) % 12 + 1
            y_target = today.year + ((today.month - i - 1) // 12)
            month_date = date(y_target, m_target, 1)
            month_name = month_date.strftime('%b %Y')
            month_labels.append(month_name)

            # count loans in this month
            # compute start and end of that month
            if m_target == 12:
                next_month = date(y_target + 1, 1, 1)
            else:
                next_month = date(y_target, m_target + 1, 1)

            c = BookLoan.query.filter(
                BookLoan.issue_date >= month_date,
                BookLoan.issue_date < next_month
            ).count()
            month_counts.append(c)

        # 3. Loan status breakdown
        active_count = BookLoan.query.filter_by(status=BookLoan.STATUS_ACTIVE).count()
        returned_ontime = BookLoan.query.filter(
            BookLoan.status == BookLoan.STATUS_RETURNED,
            BookLoan.return_date <= BookLoan.due_date
        ).count()
        returned_late = BookLoan.query.filter(
            BookLoan.status == BookLoan.STATUS_RETURNED,
            BookLoan.return_date > BookLoan.due_date
        ).count()

        loan_status_labels = ['Active Loans', 'Returned On Time', 'Returned Overdue']
        loan_status_counts = [active_count, returned_ontime, returned_late]

        return {
            'category_labels': category_labels,
            'category_counts': category_counts,
            'month_labels': month_labels,
            'month_counts': month_counts,
            'loan_status_labels': loan_status_labels,
            'loan_status_counts': loan_status_counts
        }

    @classmethod
    def get_recent_activity(cls, limit=8):
        """Fetch latest circulation records and audit logs."""
        loans = BookLoan.query.order_by(BookLoan.created_at.desc()).limit(limit).all()
        return loans
