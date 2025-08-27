import os
import json

def find_doctors(locations, specialization):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir,"..", "data", "doctors.json")
    file_path = os.path.normpath(file_path)

    with open(file_path, "r") as f:
        doctors_data = json.load(f)

    results = []
    for entry in doctors_data:
        if entry["location"] in locations and entry["specialization"] == specialization:
            results.append({
                "doctor_name": entry["doctor_name"],
                "specialization": entry["specialization"],
                "experience": entry["experience"],
                "rating": entry["rating"],
                "reviews": entry["reviews"],
                "hospital_name": entry["hospital"]["name"],
                "hospital_address": entry["hospital"]["address"],
                "hospital_contact": entry["hospital"]["contact"],
                "map_link": f"https://www.google.com/maps/search/{entry['hospital']['address'].replace(' ', '+')}"
            })
    return results



def get_nearby_locations(location):
    nearby = {
        "Gajuwaka": ["Gajuwaka", "Visakhapatnam", "NAD Junction"],
        "Hyderabad": ["Hyderabad", "Secunderabad", "Gachibowli"]
    }
    return nearby.get(location, [location])

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
    return mapping.get(disease.lower())

