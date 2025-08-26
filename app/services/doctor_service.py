import os
import json

def find_doctors(locations, specialization):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir,"..", "data", "doctors.json")
    file_path = os.path.normpath(file_path)

    with open(file_path, "r") as f:
        doctors = json.load(f)

    ddetails = [doc for doc in doctors if doc["location"] in locations and doc["specialization"] == specialization]
    return ddetails

def get_nearby_locations(location):
    # Simulated nearby locations
    nearby = {
        "Gajuwaka": ["Gajuwaka", "Visakhapatnam", "NAD Junction"],
        "Hyderabad": ["Hyderabad", "Secunderabad", "Gachibowli"]
    }
    return nearby.get(location, [location])

print(get_nearby_locations("Gajuwaka"))


doctors = [{"name": "Dr. Ramesh", "specialization": "Endocrinologist", "location": "Gajuwaka"},
 {"name": "Dr. Priya", "specialization": "General Physician", "location": "Visakhapatnam"},
 {"name": "Dr. Anil", "specialization": "Pulmonologist", "location": "NAD Junction"},
 {"name": "Dr. Sneha", "specialization": "Dermatologist", "location": "Gajuwaka"},
 {"name": "Dr. Kiran", "specialization": "Dentist", "location": "Visakhapatnam"}]


[{"name": "Dr. Ramesh",
  "specialization": "Endocrinologist",
  "location": "Gajuwaka",
  "rating": 4.7,
  "reviews": [
    "Very knowledgeable and kind.",
    "Helped me manage my diabetes effectively."]}]

def map_disease_to_specialist(disease):
    mapping = {
        "diabetes": "Endocrinologist",
        "fever": "General Physician",
        "asthma": "Pulmonologist",
        "skin rash": "Dermatologist",
        "tooth pain": "Dentist"
    }
    return mapping.get(disease)

print(map_disease_to_specialist("skin rash"))

