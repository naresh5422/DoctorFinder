# from routers import setup_routes
# from flask import Flask


# # def run_app():
# #     print("Welcome to Doctor Finder 🏥")
# #     location = input("Enter your city or location: ")
# #     disease = input("Enter your disease or symptoms: ")
# #     result = handle_request(location, disease)
# #     print("\nNearby Doctors:")
# #     for doc in result:
# #         print(f"- {doc['name']} ({doc['specialization']}) — {doc['location']}")



# def create_app():
#     app = Flask(__name__)
#     setup_routes(app)
#     return app





from flask import Flask
from extension import db, SQLALCHEMY_DATABASE_URI
from routers import setup_routes
from auth import setup_auth
from models import User



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    # app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SECRET_KEY"] = "your_secret_key"

    db.init_app(app)
    setup_routes(app)
    setup_auth(app)

    with app.app_context():
        db.create_all()

    return app

app = create_app()  


if __name__ == "__main__":
    app.run(debug=True)