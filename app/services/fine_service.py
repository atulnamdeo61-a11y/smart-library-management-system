from datetime import date, datetime
from decimal import Decimal
from flask import current_app
from app.extensions import db
from app.models.book_loan import BookLoan
from app.models.fine import Fine, FinePayment
from app.models.audit_log import AuditLog


def calculate_fine_for_loan(loan, fine_rate=None, grace_period=None):
    """
    Calculate overdue fine for a given loan using date-only arithmetic.
    Returns: (fine_amount: Decimal, overdue_days: int)
    """
    if fine_rate is None:
        fine_rate = Decimal(str(loan.fine_rate_snapshot or current_app.config.get('FINE_RATE_PER_DAY', 2.00)))
    else:
        fine_rate = Decimal(str(fine_rate))

    if grace_period is None:
        grace_period = int(current_app.config.get('FINE_GRACE_PERIOD_DAYS', 0))

    # Determine cutoff date: return date if returned, else today
    cutoff = loan.return_date if loan.return_date else date.today()

    if cutoff <= loan.due_date:
        return Decimal('0.00'), 0

    overdue_days = (cutoff - loan.due_date).days

    billable_days = max(0, overdue_days - grace_period)
    fine_amount = Decimal(billable_days) * fine_rate
    return fine_amount.quantize(Decimal('0.01')), overdue_days


class FineService:
    @staticmethod
    def format_currency(amount):
        """Format an amount with Indian Rupee symbol."""
        symbol = current_app.config.get('CURRENCY_SYMBOL', '₹')
        try:
            val = float(amount or 0)
            return f"{symbol}{val:,.2f}"
        except (ValueError, TypeError):
            return f"{symbol}0.00"

    @classmethod
    def refresh_loan_fine(cls, loan):
        """Recalculate fine for an active loan and update its database record."""
        fine = loan.fine
        if not fine:
            fine = Fine(loan_id=loan.id)
            db.session.add(fine)

        # Do not alter waived fines
        if fine.payment_status == Fine.STATUS_WAIVED:
            return fine

        fine_amount, overdue_days = calculate_fine_for_loan(loan)
        fine.calculated_amount = fine_amount
        fine.last_calculated_at = datetime.utcnow()
        fine.update_payment_status()
        return fine

    @classmethod
    def refresh_all_active_fines(cls):
        """Refresh fine calculations for all active loans."""
        active_loans = BookLoan.query.filter_by(status=BookLoan.STATUS_ACTIVE).all()
        for loan in active_loans:
            cls.refresh_loan_fine(loan)
        db.session.commit()

    @classmethod
    def record_payment(cls, fine_id, staff_user, amount, payment_method='Cash', reference_note=None):
        """
        Record a payment towards an outstanding fine.
        Validates that amount is positive and does not exceed outstanding balance.
        """
        fine = db.session.get(Fine, fine_id)
        if not fine:
            return False, "Fine record not found."

        if fine.payment_status == Fine.STATUS_WAIVED:
            return False, "Cannot record payment on a waived fine."

        try:
            amt = Decimal(str(amount))
        except Exception:
            return False, "Invalid payment amount format."

        if amt <= Decimal('0.00'):
            return False, "Payment amount must be greater than zero."

        outstanding = fine.outstanding_amount
        if amt > outstanding:
            return False, f"Payment exceeds outstanding amount of {cls.format_currency(outstanding)}."

        try:
            fine.amount_paid = (Decimal(str(fine.amount_paid or 0)) + amt).quantize(Decimal('0.01'))
            fine.update_payment_status()

            payment = FinePayment(
                fine_id=fine.id,
                recorded_by=staff_user.id,
                amount=amt,
                payment_method=payment_method,
                reference_note=reference_note
            )
            db.session.add(payment)

            AuditLog.record(
                actor_id=staff_user.id,
                action='RECORD_FINE_PAYMENT',
                entity_type='FinePayment',
                entity_id=payment.id,
                details=f"Payment of {cls.format_currency(amt)} recorded for Fine #{fine.id} (Loan #{fine.loan_id}) via {payment_method}."
            )
            db.session.commit()
            return True, f"Payment of {cls.format_currency(amt)} recorded successfully. New status: {fine.payment_status}."
        except Exception as e:
            db.session.rollback()
            return False, f"Payment recording failed: {str(e)}"

    @classmethod
    def waive_fine(cls, fine_id, admin_user, reason='Administrative waiver'):
        """Waive an outstanding fine (Admin only)."""
        fine = db.session.get(Fine, fine_id)
        if not fine:
            return False, "Fine record not found."

        if fine.payment_status in (Fine.STATUS_PAID, Fine.STATUS_WAIVED):
            return False, f"Fine is already marked as {fine.payment_status}."

        try:
            fine.payment_status = Fine.STATUS_WAIVED
            payment = FinePayment(
                fine_id=fine.id,
                recorded_by=admin_user.id,
                amount=Decimal('0.00'),
                payment_method='Waiver',
                reference_note=f"Waived by Admin #{admin_user.id}: {reason}"
            )
            db.session.add(payment)

            AuditLog.record(
                actor_id=admin_user.id,
                action='WAIVE_FINE',
                entity_type='Fine',
                entity_id=fine.id,
                details=f"Fine #{fine.id} waived by {admin_user.full_name}. Reason: {reason}"
            )
            db.session.commit()
            return True, "Fine has been waived successfully."
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to waive fine: {str(e)}"
