import os
from flask import Flask
from app.extension import db, mail
from app.config import settings
import firebase_admin
import json
from datetime import datetime
from flask_migrate import Migrate
from firebase_admin import credentials

def create_app():
    app = Flask(__name__)
    app.config.from_object(settings)
    print("🚀 Using Database URL:", os.getenv("DATABASE_URL"))
    is_development = app.config.get('FLASK_ENV', 'production').lower() == 'development'
    db_uri = app.config.get('DATABASE_URL', '')
    if is_development and ('postgresql' in db_uri):
        error_message = (
            "FATAL CONFIGURATION ERROR: You are running in a development environment, but your "
            "DATABASE_URL is set to a PostgreSQL (production) database. \n"
            "Please check your .env file and set DATABASE_URL to your local MySQL database. \n"
            "Example: DATABASE_URL=\"mysql+mysqlconnector://user:password@localhost/DoctorFinder_DB\""
        )
        raise RuntimeError(error_message)
    try:
        if not firebase_admin._apps:
            cred_value = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_value:
                if os.path.exists(cred_value):
                    cred = credentials.Certificate(cred_value)
                elif cred_value.strip().startswith('{'):
                    cred_info = json.loads(cred_value)
                    cred = credentials.Certificate(cred_info)
                else:
                    raise FileNotFoundError(f"The path specified in GOOGLE_APPLICATION_CREDENTIALS does not exist: {cred_value}")
                firebase_admin.initialize_app(cred)
                app.logger.info("Firebase Admin SDK initialized successfully.")
            else:
                app.logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set. Phone verification will be disabled.")
    except Exception as e:
        app.logger.error(f"Failed to initialize Firebase Admin SDK: {e}. Phone verification will not work.")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    @app.context_processor
    def utility_processor():
        return dict(current_year=datetime.utcnow().year)

    def month_name_filter(date_str):
        """A Jinja filter to get the abbreviated month name from a 'YYYY-MM-DD' string."""
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%b') # e.g., 'Sep'
        except (ValueError, TypeError):
            return ''
    app.jinja_env.filters['month_name'] = month_name_filter

    db.init_app(app)
    mail.init_app(app)

    # --- Load service data and AI models ---
    # This is done after db.init_app to ensure the app context and DB are available.
    with app.app_context():
        from app.services.doctor_service import load_service_data
        load_service_data()

    Migrate(app, db)
    from app.routers import setup_routes
    from app.doctor_routes import setup_doctor_routes
    setup_routes(app)
    setup_doctor_routes(app)
    return app