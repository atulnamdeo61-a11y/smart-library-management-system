from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    ROLE_ADMIN = 'admin'
    ROLE_LIBRARIAN = 'librarian'
    ROLE_STUDENT = 'student'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student', index=True)  # 'admin', 'librarian', 'student'
    student_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    course = db.Column(db.String(100), nullable=True)  # e.g., 'MCA', 'BCA', 'B.Tech Computer Science'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    book_requests = db.relationship('BookRequest', foreign_keys='BookRequest.student_id', back_populates='student', lazy='dynamic')
    loans = db.relationship('BookLoan', foreign_keys='BookLoan.student_id', back_populates='student', lazy='dynamic')
    preferences = db.relationship('StudentPreference', back_populates='student', cascade='all, delete-orphan', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', back_populates='actor', lazy='dynamic')

    def set_password(self, password: str):
        """Hash and set user password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_librarian(self) -> bool:
        return self.role == 'librarian'

    @property
    def is_student(self) -> bool:
        return self.role == 'student'

    @property
    def is_staff(self) -> bool:
        return self.role in ('admin', 'librarian')

    @property
    def effective_course(self) -> str:
        """Return student's active course of study with intelligent fallbacks."""
        if self.course and self.course.strip():
            return self.course.strip()
        # Fallback to latest ID card if available
        try:
            id_card = self.id_cards.order_by(db.desc('id')).first()
            if id_card and id_card.course_branch:
                return id_card.course_branch.strip()
        except Exception:
            pass
        return 'Computer Science / Engineering'

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
