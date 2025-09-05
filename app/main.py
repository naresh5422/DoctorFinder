import os
from flask import Flask
from extension import db, SQLALCHEMY_DATABASE_URI
from routers import setup_routes
from models import User



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

    with app.app_context():
        db.create_all()

    return app

capp = create_app()  


if __name__ == "__main__":
    capp.run(debug=True, port=5000)