import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from flask import current_app

logger = logging.getLogger(__name__)


class EmailService:
    """Service handling email delivery via Gmail SMTP with fallback for dev/demo."""

    @staticmethod
    def send_password_reset_otp(to_email: str, recipient_name: str, otp_code: str, expires_minutes: int = 10) -> tuple:
        """
        Send a 6-digit OTP email using Gmail SMTP.
        Returns: (success: bool, status_message: str)
        """
        smtp_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        username = (current_app.config.get('MAIL_USERNAME') or '').strip()
        password = (current_app.config.get('MAIL_PASSWORD') or '').strip().replace(' ', '')
        sender = (current_app.config.get('MAIL_DEFAULT_SENDER') or username or 'smartlibrary.system@gmail.com').strip()

        # If in automated testing mode or credentials missing, simulate delivery
        if current_app.config.get('TESTING') or not username or not password:
            msg_notice = f"[DEV / TEST MODE] Simulated OTP for {to_email}: {otp_code}"
            logger.info(msg_notice)
            print(f"\n==================================================")
            print(f" [GMAIL SMTP SIMULATION] PASSWORD RESET OTP")
            print(f" Recipient : {to_email} ({recipient_name})")
            print(f" OTP Code  : >>> {otp_code} <<< (Valid for {expires_minutes} mins)")
            print(f"==================================================\n")
            return True, "DEV_SIMULATION"

        # Build MIME Message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Smart Library - Password Reset OTP: {otp_code}"
        msg['From'] = f"Smart Library System <{sender}>"
        msg['To'] = to_email
        msg['Date'] = formatdate(localtime=True)

        # Plain-Text Version
        text_body = f"""Hello {recipient_name},

We received a request to reset your password for your Smart Library account ({to_email}).

Your 6-digit verification code (OTP) is:
------------------------
>>> {otp_code} <<<
------------------------

This OTP is valid for {expires_minutes} minutes. Please do not share this code with anyone.

If you did not request this password reset, please ignore this email or notify library staff immediately.

Best regards,
Smart Library Administration & Security Desk
College Campus Library
"""

        # HTML Version with Rich Styling
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
        .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }}
        .header {{ background: linear-gradient(135deg, #4361ee, #3a0ca3); color: #ffffff; padding: 28px 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
        .content {{ padding: 32px 28px; color: #2b2d42; line-height: 1.6; }}
        .greeting {{ font-size: 16px; font-weight: 600; margin-bottom: 12px; }}
        .otp-box {{ background: #f0f4ff; border: 2px dashed #4361ee; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0; }}
        .otp-code {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #4361ee; font-family: 'Courier New', Courier, monospace; display: block; }}
        .otp-expiry {{ font-size: 13px; color: #6c757d; margin-top: 8px; }}
        .note {{ font-size: 13px; color: #6c757d; background: #f8f9fa; border-left: 3px solid #ffb703; padding: 10px 14px; border-radius: 4px; margin-top: 20px; }}
        .footer {{ background: #f8f9fa; border-top: 1px solid #e9ecef; padding: 18px 24px; text-align: center; font-size: 12px; color: #8d99ae; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>&#128218; Smart Library Management</h1>
            <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">Account Security & Password Recovery</div>
        </div>
        <div class="content">
            <div class="greeting">Hello {recipient_name},</div>
            <p>We received a request to reset your password for your library account associated with <strong>{to_email}</strong>.</p>
            <p>Please use the following 6-digit One-Time Password (OTP) to complete your password reset:</p>
            
            <div class="otp-box">
                <span class="otp-code">{otp_code}</span>
                <div class="otp-expiry">&#9200; Valid for <strong>{expires_minutes} minutes</strong></div>
            </div>

            <div class="note">
                <strong>&#128274; Security Notice:</strong> Never share this OTP with anyone. Library administrators or staff will never ask for your password or verification code.
            </div>

            <p style="font-size: 13px; color: #6c757d; margin-top: 20px;">If you did not request this password reset, please ignore this email. Your current password will remain safe and unchanged.</p>
        </div>
        <div class="footer">
            &copy; 2026 Smart Library System &bull; College Minor Project<br>
            Automated message, please do not reply to this email.
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Connect and Send via SMTP
        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=12) as server:
                if use_tls:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                server.login(username, password)
                server.sendmail(sender, [to_email], msg.as_string())
            logger.info(f"Successfully dispatched OTP email to {to_email} via {smtp_server}:{smtp_port}")
            return True, "Email sent successfully via Gmail SMTP."
        except Exception as e:
            logger.error(f"Failed to send email via Gmail SMTP to {to_email}: {str(e)}")
            return False, f"SMTP Error: {str(e)}"
