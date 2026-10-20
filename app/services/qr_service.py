import os
from pathlib import Path
from urllib.parse import quote_plus
import qrcode
from PIL import Image
from flask import current_app, url_for


class QRService:
    @staticmethod
    def generate_qr_for_book(book, target_url=None):
        """
        Generate a QR code image for a given book pointing to its details page.
        Saves image into app/static/qrcodes/book_<id>.png.
        Returns the web-accessible relative path: 'qrcodes/book_<id>.png'.
        """
        qr_folder = Path(current_app.config['QR_FOLDER'])
        qr_folder.mkdir(parents=True, exist_ok=True)

        filename = f"book_{book.id}.png"
        filepath = qr_folder / filename

        # Content of QR code: direct URL to book details
        if not target_url:
            from flask import has_request_context
            if has_request_context():
                target_url = url_for('books.detail', book_id=book.id, _external=True)
            else:
                target_url = f"http://127.0.0.1:5000/books/{book.id}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(target_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1a202c", back_color="#ffffff")
        img.save(str(filepath))

        relative_path = f"qrcodes/{filename}"
        book.qr_code_path = relative_path
        return relative_path

    @staticmethod
    def generate_upi_qr(upi_id: str, payee_name: str, amount: float, note: str, reference_id: str) -> tuple:
        """
        Generate a standard dynamic UPI Payment QR Code.
        Returns (relative_file_path, raw_upi_uri).
        """
        qr_folder = Path(current_app.config['QR_FOLDER'])
        qr_folder.mkdir(parents=True, exist_ok=True)

        filename = f"upi_pay_{reference_id}.png"
        filepath = qr_folder / filename

        # Construct standard NPCI UPI URI
        clean_amount = f"{float(amount):.2f}"
        upi_uri = (
            f"upi://pay?pa={upi_id}"
            f"&pn={quote_plus(payee_name)}"
            f"&am={clean_amount}"
            f"&cu=INR"
            f"&tn={quote_plus(note)}"
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(upi_uri)
        qr.make(fit=True)

        # Generate styled QR code with deep indigo accent
        img = qr.make_image(fill_color="#1e3a8a", back_color="#ffffff")
        img.save(str(filepath))

        relative_path = f"qrcodes/{filename}"
        return relative_path, upi_uri

    @staticmethod
    def generate_id_card_qr(card) -> str:
        """
        Generate a high-density QR code for the student's physical/digital ID card.
        Encodes student library credentials for barcode/QR scanner scanning at circulation desk.
        """
        qr_folder = Path(current_app.config['QR_FOLDER'])
        qr_folder.mkdir(parents=True, exist_ok=True)

        filename = f"idcard_{card.card_number.replace('-', '_')}.png"
        filepath = qr_folder / filename

        # Scannable payload for circulation desk
        if card.student and card.student.is_staff:
            payload = (
                f"SMART_LIBRARY_STAFF_ID:{card.card_number}|"
                f"NAME:{card.student.full_name}|"
                f"ROLE:{card.student.role.upper()}|"
                f"CODE:{card.roll_number}|"
                f"DEPT:{card.course_branch}|"
                f"EXP:{card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else 'PERMANENT'}"
            )
        else:
            payload = (
                f"SMART_LIBRARY_ID:{card.card_number}|"
                f"STUDENT:{card.student.full_name}|"
                f"ROLL:{card.roll_number}|"
                f"COURSE:{card.course_branch}|"
                f"EXP:{card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else 'N/A'}"
            )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        img.save(str(filepath))

        relative_path = f"qrcodes/{filename}"
        card.qr_code_path = relative_path
        return relative_path
