from routers import setup_routes
from flask import Flask


# def run_app():
#     print("Welcome to Doctor Finder 🏥")
#     location = input("Enter your city or location: ")
#     disease = input("Enter your disease or symptoms: ")
#     result = handle_request(location, disease)
#     print("\nNearby Doctors:")
#     for doc in result:
#         print(f"- {doc['name']} ({doc['specialization']}) — {doc['location']}")



def create_app():
    app = Flask(__name__)
    setup_routes(app)
    return app

app = create_app()  


if __name__ == "__main__":
    app.run(debug=True)
