from app.extensions import db


class StudentPreference(db.Model):
    __tablename__ = 'student_preferences'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'category_id', name='uq_student_category_pref'),
    )

    # Relationships
    student = db.relationship('User', back_populates='preferences')
    category = db.relationship('Category', back_populates='student_preferences')

    def __repr__(self):
        return f'<StudentPreference student={self.student_id} category={self.category_id}>'
