from datetime import datetime
import json
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    actor = db.relationship('User', back_populates='audit_logs')

    @classmethod
    def record(cls, actor_id, action, entity_type, entity_id=None, details=None):
        """Helper to create and save an audit log entry."""
        if isinstance(details, (dict, list)):
            details_str = json.dumps(details)
        else:
            details_str = str(details) if details is not None else None

        entry = cls(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_str
        )
        db.session.add(entry)
        return entry

    def __repr__(self):
        return f'<AuditLog action={self.action} entity={self.entity_type}:{self.entity_id}>'
