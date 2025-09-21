from flask_sqlalchemy import SQLAlchemy
import os
from flask import Flask, current_app
from flask_mail import Mail
from functools import wraps
from flask import session, redirect, url_for, flash, request
from markupsafe import Markup

db = SQLAlchemy()
mail = Mail()

def check_gmail_app_password():
    """
    Checks if Gmail is used and if the password looks like an App Password.
    Returns True if the check passes, False otherwise.
    Flashes a message on failure.
    """
    if current_app.config.get('MAIL_SERVER') == 'smtp.gmail.com':
        mail_password = current_app.config.get('MAIL_PASSWORD', '')
        # Google App Passwords are 16 characters long and don't contain spaces.
        if ' ' in mail_password or (mail_password and len(mail_password) != 16):
            flash(Markup("Gmail Configuration Error: Please use a 16-character <strong>App Password</strong>. Your regular password will not work. <a href='https://myaccount.google.com/apppasswords' target='_blank' class='alert-link'>Generate one here</a>."), "danger")
            return False
    return True


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'patient_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def doctor_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor_id' not in session:
            flash("Please log in as a doctor to continue.", "warning")
            return redirect(url_for('doctor_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def doctor_verified_required(f):
    """
    A decorator to ensure that a doctor has verified both email and mobile
    to access certain features.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Import here to avoid potential circular dependencies
        from .models import Doctor

        if 'doctor_id' not in session:
            # This should be handled by doctor_login_required, but it's a good safeguard.
            return redirect(url_for('doctor_login'))

        doctor = Doctor.query.get(session['doctor_id'])
        if not doctor:
            flash("Doctor profile not found. Please log in again.", "danger")
            session.pop("doctor_id", None) # Clean up bad session
            return redirect(url_for('doctor_login'))

        if not getattr(doctor, 'email_verified', False) or not getattr(doctor, 'mobile_verified', False):
            missing = [item for item, verified in [('email', getattr(doctor, 'email_verified', False)), ('mobile number', getattr(doctor, 'mobile_verified', False))] if not verified]
            flash(f"Please verify your { ' and '.join(missing) } to access this feature. You can do this from your profile.", "warning")
            return redirect(url_for('my_profile'))

        return f(*args, **kwargs)
    return decorated_function
