import os
from flask import Flask
from app.extension import db, mail
from app.config import settings
import firebase_admin
from datetime import datetime
from flask_migrate import Migrate
from firebase_admin import credentials


def create_app():
    app = Flask(__name__)

    # Load all configurations from the settings object in config.py
    app.config.from_object(settings)

    # --- BEGIN: Firebase Admin SDK Initialization ---
    # The GOOGLE_APPLICATION_CREDENTIALS env var should point to the service account file.
    try:
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not firebase_admin._apps:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            app.logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        app.logger.error(f"Failed to initialize Firebase Admin SDK: {e}. Phone verification will not work.")
    # --- END: Firebase Admin SDK Initialization ---

    # Ensure the upload folder from the config exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.context_processor
    def utility_processor():
        return dict(current_year=datetime.utcnow().year)

    db.init_app(app)
    mail.init_app(app) # Initialize mail
    Migrate(app, db) # Initialize Flask-Migrate

    # --- BEGIN BUG FIX: Defer route imports to prevent circular dependencies ---
    from app.routers import setup_routes
    from app.doctor_routes import setup_doctor_routes
    
    setup_routes(app)
    setup_doctor_routes(app)
    # --- END BUG FIX ---

    return app