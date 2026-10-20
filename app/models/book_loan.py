from datetime import datetime, date
from app.extensions import db


class BookLoan(db.Model):
    __tablename__ = 'book_loans'

    STATUS_ACTIVE = 'Active'
    STATUS_RETURNED = 'Returned'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issue_date = db.Column(db.Date, default=date.today, nullable=False)
    due_date = db.Column(db.Date, nullable=False, index=True)
    return_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default=STATUS_ACTIVE, nullable=False, index=True)
    fine_rate_snapshot = db.Column(db.Numeric(8, 2), default=2.00, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], back_populates='loans')
    book = db.relationship('Book', back_populates='loans')
    issuer = db.relationship('User', foreign_keys=[issued_by])
    fine = db.relationship('Fine', back_populates='loan', uselist=False, cascade='all, delete-orphan')

    @property
    def is_overdue(self) -> bool:
        if self.status == self.STATUS_ACTIVE:
            return date.today() > self.due_date
        if self.return_date and self.due_date:
            return self.return_date > self.due_date
        return False

    @property
    def overdue_days(self) -> int:
        cutoff_date = self.return_date if self.return_date else date.today()
        if cutoff_date > self.due_date:
            return (cutoff_date - self.due_date).days
        return 0

    def __repr__(self):
        return f'<BookLoan id={self.id} student={self.student_id} book={self.book_id} status={self.status}>'
