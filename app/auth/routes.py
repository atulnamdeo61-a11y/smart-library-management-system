import uuid
from pathlib import Path
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.password_reset_otp import PasswordResetOTP
from app.services.email_service import EmailService
from app.auth.forms import (
    LoginForm,
    RegistrationForm,
    EditProfileForm,
    ChangePasswordForm,
    ForgotPasswordForm,
    ResetPasswordForm
)

auth_bp = Blueprint('auth', __name__)


def is_safe_url(target):
    """Check if redirect URL is safe to prevent open redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc or not test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_librarian:
            return redirect(url_for('librarian.dashboard'))
        return redirect(url_for('student.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(User.email.ilike(email)).first()

        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('auth/login.html', form=form)

        if not user.is_active:
            flash('Your account has been deactivated. Please contact the library administrator.', 'warning')
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.full_name}!', 'success')

        AuditLog.record(
            actor_id=user.id,
            action='USER_LOGIN',
            entity_type='User',
            entity_id=user.id,
            details=f"User {user.email} logged in successfully."
        )
        db.session.commit()

        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)

        # Role-based landing redirects
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif user.is_librarian:
            return redirect(url_for('librarian.dashboard'))
        return redirect(url_for('student.dashboard'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Enforce student role for all public registrations
            new_student = User(
                full_name=form.full_name.data.strip(),
                email=form.email.data.strip().lower(),
                student_id=form.student_id.data.strip().upper(),
                phone=form.phone.data.strip() if form.phone.data else None,
                role='student',
                is_active=True
            )
            new_student.set_password(form.password.data)
            db.session.add(new_student)
            db.session.flush()

            AuditLog.record(
                actor_id=new_student.id,
                action='STUDENT_REGISTRATION',
                entity_type='User',
                entity_id=new_student.id,
                details=f"New student {new_student.full_name} ({new_student.student_id}) registered."
            )
            db.session.commit()

            flash('Registration successful! You can now log in with your credentials.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration. Please try again.', 'danger')

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    user_id = current_user.id
    email = current_user.email
    logout_user()
    AuditLog.record(
        actor_id=user_id,
        action='USER_LOGOUT',
        entity_type='User',
        entity_id=user_id,
        details=f"User {email} logged out."
    )
    db.session.commit()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Universal Profile page for all account types (Student, Librarian, Admin)."""
    profile_form = EditProfileForm(original_email=current_user.email, obj=current_user)
    password_form = ChangePasswordForm()

    if request.method == 'POST' and profile_form.validate_on_submit():
        current_user.full_name = profile_form.full_name.data.strip()
        current_user.email = profile_form.email.data.strip().lower()
        current_user.phone = profile_form.phone.data.strip() if profile_form.phone.data else None

        # Check for profile image removal
        if profile_form.remove_image.data:
            if current_user.profile_image:
                old_file = Path(current_app.root_path) / 'static' / current_user.profile_image
                if old_file.exists():
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
                current_user.profile_image = None

        # Check for new profile image upload
        image_file = profile_form.profile_image.data
        if image_file and hasattr(image_file, 'filename') and image_file.filename:
            raw_ext = Path(image_file.filename).suffix.lower()
            if raw_ext in ('.png', '.jpg', '.jpeg', '.webp'):
                clean_name = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{raw_ext}"
                avatars_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'avatars'
                avatars_dir.mkdir(parents=True, exist_ok=True)
                dest_path = avatars_dir / clean_name
                image_file.save(str(dest_path))

                # Remove old custom image file if existed
                if current_user.profile_image and current_user.profile_image != f"uploads/avatars/{clean_name}":
                    old_file = Path(current_app.root_path) / 'static' / current_user.profile_image
                    if old_file.exists():
                        try:
                            old_file.unlink()
                        except Exception:
                            pass

                current_user.profile_image = f"uploads/avatars/{clean_name}"

        AuditLog.record(
            actor_id=current_user.id,
            action='PROFILE_UPDATE',
            entity_type='User',
            entity_id=current_user.id,
            details=f"User {current_user.id} ({current_user.role}) updated profile: name='{current_user.full_name}', email='{current_user.email}'."
        )
        db.session.commit()
        flash('Your profile details and image have been updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html',
                           profile_form=profile_form,
                           password_form=password_form,
                           active_tab='profile',
                           user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Universal Change Password page for all account types (Student, Librarian, Admin)."""
    profile_form = EditProfileForm(original_email=current_user.email, obj=current_user)
    password_form = ChangePasswordForm()

    if request.method == 'POST' and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data):
            password_form.current_password.errors.append('Current password is incorrect. Please try again.')
        elif password_form.current_password.data == password_form.new_password.data:
            password_form.new_password.errors.append('New password must be different from your current password.')
        else:
            current_user.set_password(password_form.new_password.data)
            AuditLog.record(
                actor_id=current_user.id,
                action='PASSWORD_CHANGE',
                entity_type='User',
                entity_id=current_user.id,
                details=f"User {current_user.email} ({current_user.role}) changed account password successfully."
            )
            db.session.commit()
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('auth.change_password'))

    return render_template('auth/profile.html',
                           profile_form=profile_form,
                           password_form=password_form,
                           active_tab='password',
                           user=current_user)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request OTP for password reset via email."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = ForgotPasswordForm()
    if request.method == 'GET':
        prefill_email = request.args.get('email', '').strip()
        if prefill_email:
            form.email.data = prefill_email

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(User.email.ilike(email)).first()

        if not user:
            flash(f"No registered account found with email '{email}'. Please check your spelling or register.", 'danger')
            return render_template('auth/forgot_password.html', form=form)

        if not user.is_active:
            flash("Your account has been deactivated. Please contact the library administrator.", 'warning')
            return render_template('auth/forgot_password.html', form=form)

        # Generate fresh OTP valid for 10 minutes
        otp_code = PasswordResetOTP.generate_otp(
            email=user.email,
            expires_minutes=10,
            ip_address=request.remote_addr
        )

        # Dispatch via EmailService (Gmail SMTP)
        success, status_msg = EmailService.send_password_reset_otp(
            to_email=user.email,
            recipient_name=user.full_name,
            otp_code=otp_code,
            expires_minutes=10
        )

        AuditLog.record(
            actor_id=user.id,
            action='OTP_REQUESTED',
            entity_type='User',
            entity_id=user.id,
            details=f"Password reset OTP generated for {user.email}."
        )
        db.session.commit()

        if status_msg == "DEV_SIMULATION":
            flash(f"A 6-digit verification code has been generated for {user.email}! [DEV / VIVA MODE: Your OTP is {otp_code} (Valid for 10 mins)]", 'info')
        elif success:
            flash(f"A 6-digit verification code has been dispatched to {user.email} via Gmail SMTP! Please check your inbox or spam folder.", 'success')
        else:
            flash(f"Email delivery notice: {status_msg}. [DEV FALLBACK OTP: {otp_code} (Valid 10 mins)]", 'warning')

        return redirect(url_for('auth.reset_password', email=user.email))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Verify OTP and update user password."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = ResetPasswordForm()
    email_arg = request.args.get('email', '').strip()

    if request.method == 'GET' and email_arg:
        form.email.data = email_arg

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        otp = form.otp.data.strip()
        new_password = form.password.data

        user = User.query.filter(User.email.ilike(email)).first()
        if not user:
            form.email.errors.append('No account found with this email address.')
            return render_template('auth/reset_password.html', form=form)

        # Verify OTP
        is_valid_otp = PasswordResetOTP.verify_otp(email, otp)
        if not is_valid_otp:
            form.otp.errors.append('Invalid or expired OTP code. Please enter the correct code or request a new one.')
            return render_template('auth/reset_password.html', form=form)

        # Set new password
        user.set_password(new_password)

        AuditLog.record(
            actor_id=user.id,
            action='PASSWORD_RESET_SUCCESS',
            entity_type='User',
            entity_id=user.id,
            details=f"User {user.email} successfully reset their password using verified OTP."
        )
        db.session.commit()

        flash('Your password has been successfully reset! Please sign in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)


