from datetime import datetime
from app.extensions import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    books = db.relationship('Book', back_populates='category', lazy='dynamic')
    student_preferences = db.relationship('StudentPreference', back_populates='category', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'
