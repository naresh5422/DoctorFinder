import os
from flask import Flask
from app.extension import db, SQLALCHEMY_DATABASE_URI
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
    # os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # Optional: restrict file size (2 MB here)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    db.init_app(app)
    setup_routes(app)
    setup_doctor_routes(app)

    with app.app_context():
        db.create_all()

    return app