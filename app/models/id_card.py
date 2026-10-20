from datetime import datetime, date, timedelta
from decimal import Decimal
import uuid
from app.extensions import db


class StudentIdCard(db.Model):
    """Represents a student library ID card application, payment, and issued digital card."""
    __tablename__ = 'student_id_cards'

    STATUS_PENDING = 'Pending'
    STATUS_APPROVED = 'Approved'
    STATUS_REJECTED = 'Rejected'

    PAYMENT_PENDING = 'Pending'
    PAYMENT_PAID = 'Paid'
    PAYMENT_WAIVED = 'Waived'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    roll_number = db.Column(db.String(50), nullable=False, index=True)
    course_branch = db.Column(db.String(120), nullable=False)
    academic_year = db.Column(db.String(50), nullable=False)
    blood_group = db.Column(db.String(10), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)

    card_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    barcode_data = db.Column(db.String(128), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    upi_qr_path = db.Column(db.String(255), nullable=True)

    fee_amount = db.Column(db.Numeric(10, 2), default=Decimal('50.00'), nullable=False)
    payment_status = db.Column(db.String(20), default='Pending', nullable=False)
    payment_method = db.Column(db.String(30), default='UPI', nullable=False)
    payment_reference = db.Column(db.String(64), nullable=True)  # 12-digit UPI UTR
    paid_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), default='Pending', nullable=False)  # 'Pending', 'Approved', 'Rejected'
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_remarks = db.Column(db.Text, nullable=True)

    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], backref=db.backref('id_cards', lazy='dynamic', cascade='all, delete-orphan'))
    approver = db.relationship('User', foreign_keys=[approved_by])

    @classmethod
    def generate_card_number(cls, roll_number: str) -> str:
        """Generate a structured, unique Library ID Card identification number."""
        clean_roll = (roll_number or 'STU').replace(' ', '').upper()
        unique_suffix = uuid.uuid4().hex[:6].upper()
        current_yr = datetime.utcnow().year
        return f"LIB-{current_yr}-{clean_roll}-{unique_suffix}"

    @property
    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    @property
    def is_paid(self) -> bool:
        return self.payment_status in (self.PAYMENT_PAID, self.PAYMENT_WAIVED)

    @property
    def is_active(self) -> bool:
        if not self.is_approved:
            return False
        if self.expiry_date and self.expiry_date < date.today():
            return False
        return True

    def approve(self, staff_user_id: int, validity_years: int = 3):
        """Approve card, set issue date, and set expiry date."""
        self.status = self.STATUS_APPROVED
        self.approved_by = staff_user_id
        self.approved_at = datetime.utcnow()
        self.issue_date = date.today()
        self.expiry_date = date.today() + timedelta(days=validity_years * 365)
        self.rejection_remarks = None

    def reject(self, staff_user_id: int, remarks: str):
        """Reject card with feedback remarks."""
        self.status = self.STATUS_REJECTED
        self.approved_by = staff_user_id
        self.approved_at = datetime.utcnow()
        self.rejection_remarks = remarks

    def record_upi_payment(self, utr_reference: str):
        """Record UPI payment UTR submitted by student."""
        self.payment_reference = utr_reference.strip()
        self.payment_status = self.PAYMENT_PAID
        self.payment_method = 'UPI'
        self.paid_at = datetime.utcnow()

    def __repr__(self):
        return f"<StudentIdCard {self.card_number} (Student: {self.roll_number}, Status: {self.status})>"
