import json
# from config import DATA_PATH

def find_doctors(locations, specialization):
    with open("data/doctors.json", "r") as f:
        doctors = json.load(f)
    return [
        doc for doc in doctors
        if doc["location"] in locations and doc["specialization"] == specialization
    ]
