from routers import handle_request

def run_app():
    print("Welcome to Doctor Finder 🏥")
    location = input("Enter your city or location: ")
    disease = input("Enter your disease or symptoms: ")
    result = handle_request(location, disease)
    print("\nNearby Doctors:")
    for doc in result:
        print(f"- {doc['name']} ({doc['specialization']}) — {doc['location']}")


if __name__ == "__main__":
    run_app()