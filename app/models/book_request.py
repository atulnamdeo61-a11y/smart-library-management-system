from datetime import datetime
from app.extensions import db


class BookRequest(db.Model):
    __tablename__ = 'book_requests'

    STATUS_PENDING = 'Pending'
    STATUS_APPROVED = 'Approved'
    STATUS_REJECTED = 'Rejected'
    STATUS_CANCELLED = 'Cancelled'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False, index=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], back_populates='book_requests')
    book = db.relationship('Book', back_populates='requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<BookRequest id={self.id} student={self.student_id} book={self.book_id} status={self.status}>'
