from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from app.models.book import Book


class BookForm(FlaskForm):
    title = StringField('Book Title', validators=[DataRequired(), Length(max=255)])
    author = StringField('Author', validators=[DataRequired(), Length(max=255)])
    isbn = StringField('ISBN (10 or 13 digits)', validators=[Optional(), Length(max=30)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired(message='Please select a category.')])
    publisher = StringField('Publisher', validators=[Optional(), Length(max=255)])
    publication_year = IntegerField('Publication Year', validators=[Optional(), NumberRange(min=1000, max=2100)])
    shelf_location = StringField('Shelf / Rack Location (e.g., Rack A-3)', validators=[Optional(), Length(max=50)])
    total_copies = IntegerField('Total Copies', default=1, validators=[DataRequired(), NumberRange(min=1, message='Must be at least 1 copy.')])
    available_copies = IntegerField('Available Copies', default=1, validators=[NumberRange(min=0, message='Cannot be negative.')])
    description = TextAreaField('Description / Synopsis', validators=[Optional()])
    cover_image = FileField('Book Cover Image (Optional)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Only JPG, PNG, and WEBP image files are allowed.')
    ])
    submit = SubmitField('Save Book')

    def __init__(self, original_book_id=None, *args, **kwargs):
        super(BookForm, self).__init__(*args, **kwargs)
        self.original_book_id = original_book_id

    def validate_available_copies(self, field):
        if self.total_copies.data is not None and field.data is not None:
            if field.data > self.total_copies.data:
                raise ValidationError('Available copies cannot exceed total copies.')

    def validate_isbn(self, field):
        if field.data and field.data.strip():
            isbn_clean = field.data.strip()
            query = Book.query.filter(Book.isbn == isbn_clean)
            if self.original_book_id:
                query = query.filter(Book.id != self.original_book_id)
            if query.first():
                raise ValidationError('Another book with this ISBN already exists.')


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Category')
