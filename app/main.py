import os
from flask import Flask
from app.extension import db, SQLALCHEMY_DATABASE_URI, mail
from app.routers import setup_routes
from app.doctor_routes import setup_doctor_routes
from app.models import Patient



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SECRET_KEY"] = "your_secret_key"
    # Configure Upload Folder
    app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
    # Make sure the folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # Optional: restrict file size (2 MB here)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    
    # --- Email Configuration ---
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    # FOR DEVELOPMENT ONLY: Replace with your actual credentials from Google.
    app.config['MAIL_USERNAME'] = "t.naresh5422@gmail.com"
    app.config['MAIL_PASSWORD'] = "thesixteenletterpassword"      # <-- REPLACE with your 16-character App Password
    app.config['MAIL_DEFAULT_SENDER'] = "t.naresh5422@gmail.com"

    # --- Twilio Configuration for SMS---
    # IMPORTANT: Replace these placeholders with your actual Twilio credentials.
    app.config['TWILIO_ACCOUNT_SID'] = os.getenv("TWILIO_ACCOUNT_SID")
    app.config['TWILIO_AUTH_TOKEN'] = os.getenv("TWILIO_AUTH_TOKEN")
    app.config['TWILIO_PHONE_NUMBER'] = os.getenv("TWILIO_PHONE_NUMBER") # <-- REPLACE with your Twilio phone number

    db.init_app(app)
    mail.init_app(app) # Initialize mail

    setup_routes(app)
    setup_doctor_routes(app)

    with app.app_context():
        db.create_all()

    return app