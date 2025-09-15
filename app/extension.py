from flask_sqlalchemy import SQLAlchemy
import os
from flask import Flask
from functools import wraps
from flask import session, redirect, url_for, flash

db = SQLAlchemy()
app = Flask(__name__)

# config.py
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://root:Sulochana%40522@127.0.0.1:3306/DoctorFinder_DB"
SQLALCHEMY_TRACK_MODIFICATIONS = False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'patient_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
