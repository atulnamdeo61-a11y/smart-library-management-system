import secrets
from datetime import datetime, timedelta
from app.extensions import db


class PasswordResetOTP(db.Model):
    """Stores one-time password (OTP) tokens for password reset verification."""
    __tablename__ = 'password_reset_otps'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    otp_code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)

    @classmethod
    def generate_otp(cls, email: str, expires_minutes: int = 10, ip_address: str = None) -> str:
        """Invalidate previous unused OTPs for this email and generate a fresh 6-digit OTP."""
        email_clean = email.strip().lower()

        # Mark previous unused OTPs for this email as used/expired
        cls.query.filter(
            cls.email == email_clean,
            cls.is_used == False
        ).update({'is_used': True})

        # Generate a cryptographically secure 6-digit numeric OTP (100000 - 999999)
        code = str(secrets.randbelow(900000) + 100000)

        record = cls(
            email=email_clean,
            otp_code=code,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=expires_minutes),
            is_used=False,
            ip_address=ip_address
        )
        db.session.add(record)
        db.session.commit()
        return code

    @classmethod
    def verify_otp(cls, email: str, code: str) -> bool:
        """Verify whether the OTP matches, has not expired, and has not been used."""
        email_clean = email.strip().lower()
        code_clean = code.strip()

        record = cls.query.filter(
            cls.email == email_clean,
            cls.otp_code == code_clean,
            cls.is_used == False,
            cls.expires_at >= datetime.utcnow()
        ).order_by(cls.created_at.desc()).first()

        if record:
            record.is_used = True
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return f'<PasswordResetOTP {self.email} (used={self.is_used})>'
