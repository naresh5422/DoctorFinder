from flask import Flask
from extension import db, SQLALCHEMY_DATABASE_URI
from routers import setup_routes
from models import User



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    # app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SECRET_KEY"] = "your_secret_key"

    db.init_app(app)
    setup_routes(app)

    with app.app_context():
        db.create_all()

    return app

capp = create_app()  


if __name__ == "__main__":
    capp.run(debug=True, port=5000)