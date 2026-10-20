from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


def role_required(allowed_roles):
    """
    Decorator to restrict access to users with specific role(s).
    allowed_roles: string (single role) or iterable of role strings.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this resource.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in allowed_roles:
                flash('Access Denied: You do not have permission to access this area.', 'danger')
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to restrict access to administrator only."""
    return role_required('admin')(f)


def staff_required(f):
    """Decorator to restrict access to staff (admin or librarian)."""
    return role_required(['admin', 'librarian'])(f)


def student_required(f):
    """Decorator to restrict access to student only."""
    return role_required('student')(f)
