from datetime import datetime
from app.extensions import db


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(30), unique=True, nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    author = db.Column(db.String(255), nullable=False, index=True)
    publisher = db.Column(db.String(255), nullable=True)
    publication_year = db.Column(db.Integer, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    shelf_location = db.Column(db.String(50), nullable=True)
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    cover_image_path = db.Column(db.String(255), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    category = db.relationship('Category', back_populates='books')
    requests = db.relationship('BookRequest', back_populates='book', lazy='dynamic')
    loans = db.relationship('BookLoan', back_populates='book', lazy='dynamic')

    @property
    def is_available(self) -> bool:
        return self.available_copies > 0 and self.is_active

    @property
    def borrowed_copies(self) -> int:
        return max(0, self.total_copies - self.available_copies)

    def __repr__(self):
        return f'<Book {self.title} by {self.author}>'
