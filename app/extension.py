from flask_sqlalchemy import SQLAlchemy
import os
from flask import Flask
from flask_mail import Mail
from functools import wraps
from flask import session, redirect, url_for, flash, request

db = SQLAlchemy()
mail = Mail()
app = Flask(__name__)

# config.py
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://root:Sulochana%40522@127.0.0.1:3306/DoctorFinder_DB"
SQLALCHEMY_TRACK_MODIFICATIONS = False

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
