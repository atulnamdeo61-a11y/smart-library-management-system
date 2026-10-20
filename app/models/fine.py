from datetime import datetime
from decimal import Decimal
from app.extensions import db


class Fine(db.Model):
    __tablename__ = 'fines'

    STATUS_NO_FINE = 'No Fine'
    STATUS_PENDING = 'Pending'
    STATUS_PARTIALLY_PAID = 'Partially Paid'
    STATUS_PAID = 'Paid'
    STATUS_WAIVED = 'Waived'

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('book_loans.id'), unique=True, nullable=False, index=True)
    calculated_amount = db.Column(db.Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    amount_paid = db.Column(db.Numeric(8, 2), default=Decimal('0.00'), nullable=False)
    payment_status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False, index=True)
    last_calculated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    loan = db.relationship('BookLoan', back_populates='fine')
    payments = db.relationship('FinePayment', back_populates='fine', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def outstanding_amount(self) -> Decimal:
        if self.payment_status == self.STATUS_WAIVED:
            return Decimal('0.00')
        calc = Decimal(str(self.calculated_amount or 0))
        paid = Decimal(str(self.amount_paid or 0))
        return max(Decimal('0.00'), calc - paid)

    def update_payment_status(self):
        """Update payment status based on paid vs calculated amounts."""
        if self.payment_status == self.STATUS_WAIVED:
            return
        calc = Decimal(str(self.calculated_amount or 0))
        paid = Decimal(str(self.amount_paid or 0))

        if calc == Decimal('0.00'):
            self.payment_status = self.STATUS_NO_FINE
        elif paid >= calc:
            self.payment_status = self.STATUS_PAID
        elif paid > Decimal('0.00'):
            self.payment_status = self.STATUS_PARTIALLY_PAID
        else:
            self.payment_status = self.STATUS_PENDING

    def __repr__(self):
        return f'<Fine id={self.id} loan_id={self.loan_id} calc={self.calculated_amount} paid={self.amount_paid}>'


class FinePayment(db.Model):
    __tablename__ = 'fine_payments'

    id = db.Column(db.Integer, primary_key=True)
    fine_id = db.Column(db.Integer, db.ForeignKey('fines.id'), nullable=False, index=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(8, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    payment_method = db.Column(db.String(50), default='Cash', nullable=False)
    reference_note = db.Column(db.Text, nullable=True)

    # Relationships
    fine = db.relationship('Fine', back_populates='payments')
    recorder = db.relationship('User', foreign_keys=[recorded_by])

    def __repr__(self):
        return f'<FinePayment id={self.id} fine_id={self.fine_id} amount={self.amount}>'
