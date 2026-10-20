from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User


class LoginForm(FlaskForm):
    email = StringField('College Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('College Email', validators=[DataRequired(), Email(), Length(max=120)])
    student_id = StringField('Student / Roll ID', validators=[DataRequired(), Length(min=3, max=50)])
    phone = StringField('Phone Number (Optional)', validators=[Length(max=20)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register as Student')

    def validate_email(self, email):
        user = User.query.filter(User.email.ilike(email.data.strip())).first()
        if user:
            raise ValidationError('This email address is already registered. Please log in or use another email.')

    def validate_student_id(self, student_id):
        user = User.query.filter(User.student_id.ilike(student_id.data.strip())).first()
        if user:
            raise ValidationError('This Student ID / Roll Number is already registered.')


class EditProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(message='Full name is required.'),
        Length(min=2, max=100, message='Full name must be between 2 and 100 characters.')
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message='Email address is required.'),
        Email(message='Please enter a valid email address.'),
        Length(max=120)
    ])
    phone = StringField('Phone Number (Optional)', validators=[
        Length(max=20, message='Phone number cannot exceed 20 characters.')
    ])
    profile_image = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Only image files (JPG, PNG, WEBP) are allowed.')
    ])
    remove_image = BooleanField('Remove Current Picture')
    submit = SubmitField('Save Profile Changes')

    def __init__(self, original_email=None, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_email = original_email

    def validate_email(self, email):
        cleaned_email = email.data.strip().lower()
        if self.original_email and cleaned_email == self.original_email.lower():
            return
        user = User.query.filter(User.email.ilike(cleaned_email)).first()
        if user:
            raise ValidationError('This email address is already in use by another account.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required.')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='New password is required.'),
        Length(min=6, message='New password must be at least 6 characters long.')
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password.'),
        EqualTo('new_password', message='New password and confirmation must match.')
    ])
    submit = SubmitField('Update Password')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Registered College Email', validators=[
        DataRequired(message='Please enter your registered email address.'),
        Email(message='Please enter a valid email address.')
    ])
    submit = SubmitField('Send Verification OTP')


class ResetPasswordForm(FlaskForm):
    email = StringField('Registered Email', validators=[
        DataRequired(message='Email is required.'),
        Email(message='Please enter a valid email address.')
    ])
    otp = StringField('6-Digit OTP Code', validators=[
        DataRequired(message='Please enter the 6-digit OTP code sent to your email.'),
        Length(min=6, max=6, message='OTP code must be exactly 6 digits.')
    ])
    password = PasswordField('New Password', validators=[
        DataRequired(message='Please enter your new password.'),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password.'),
        EqualTo('password', message='New password and confirmation must match.')
    ])
    submit = SubmitField('Reset Password & Sign In')


