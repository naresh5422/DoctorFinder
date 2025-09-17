import os
import json
import random
from app.extension import db
from app.models import Doctor

def find_doctors(locations, specialization):
    # This function now reads from the database to be consistent.
    doctors_db = Doctor.query.filter(
        Doctor.location.in_(locations),
        Doctor.specialization == specialization
    ).all()

    results = []
    for doc in doctors_db:
        results.append({
            "doctor_name": doc.doctor_name,
            "specialization": doc.specialization,
            "experience": doc.experience,
            "rating": doc.rating,
            "reviews": doc.review_texts,
            "hospital_name": doc.hospital_name,
            "hospital_address": doc.hospital_address,
            "hospital_contact": doc.hospital_contact,
            "map_link": f"https://www.google.com/maps/search/{doc.hospital_address.replace(' ', '+')}" if doc.hospital_address else ""
        })
    return results


def find_hospitals(locations):
    # This function now reads from the database to ensure data consistency.
    # NOTE: Hospital services are randomly generated as they are not stored in the database.
    hospital_services = [
        "24/7 Emergency Care", "ICU", "Cardiology", "Neurology", "Orthopedics",
        "Oncology", "Pediatrics", "Gynecology", "Radiology", "Pharmacy",
        "Ambulance Service", "General Surgery", "Diagnostics Lab"
    ]

    # Find distinct hospitals in the given locations from the Doctor table
    hospitals_db = db.session.query(
        Doctor.hospital_name,
        Doctor.hospital_address,
        Doctor.hospital_contact,
        Doctor.location
    ).filter(Doctor.location.in_(locations), Doctor.hospital_name != None).distinct().all()

    hospitals = []
    for h in hospitals_db:
        hospitals.append({
            "name": h.hospital_name,
            "address": h.hospital_address,
            "contact": h.hospital_contact,
            "location": h.location,
            "map_link": f"https://www.google.com/maps/search/{h.hospital_address.replace(' ', '+')}" if h.hospital_address else "",
            "services": random.sample(hospital_services, k=random.randint(4, 7))
        })
    
    return hospitals


def get_featured_hospitals(limit=3):
    # This function now reads from the database to ensure data consistency.
    # NOTE: Hospital services are randomly generated as they are not stored in the database.
    hospital_services = [
        "24/7 Emergency Care", "ICU", "Cardiology", "Neurology", "Orthopedics",
        "Oncology", "Pediatrics", "Gynecology", "Radiology", "Pharmacy",
        "Ambulance Service", "General Surgery", "Diagnostics Lab"
    ]

    # Get all unique hospitals from the Doctor table
    all_hospitals_db = db.session.query(
        Doctor.hospital_name, 
        Doctor.hospital_address,
        Doctor.location
    ).filter(Doctor.hospital_name != None).distinct().all()
    
    # Convert to list of dicts
    unique_hospitals = [
        {
            "name": h.hospital_name,
            "address": h.hospital_address,
            "location": h.location,
            "services": random.sample(hospital_services, k=random.randint(4, 7))
        } for h in all_hospitals_db
    ]

    random.shuffle(unique_hospitals)
    
    return unique_hospitals[:limit]

def get_nearby_locations(location):
    nearby = {
        "Gajuwaka": ["Gajuwaka", "Visakhapatnam", "NAD Junction", "Malkapuram"],
        "Hyderabad": ["Hyderabad", "Secunderabad", "Gachibowli", "Madhapur", "Kukatpally"],
        "Tirupati": ["Tirupati", "Renigunta", "Chandragiri", "Mangalam"],
        "Chennai": ["Chennai", "Velachery", "Tambaram", "T Nagar"],
        "Bangalore": ["Bangalore", "Whitefield", "Electronic City", "Indiranagar", "HSR Layout"],
        "Vijayawada": ["Vijayawada", "Benz Circle", "Governorpet", "Gollapudi"],
        "Delhi": ["Delhi", "Dwarka", "Saket", "Karol Bagh"],
        "Mumbai": ["Mumbai", "Andheri", "Bandra", "Dadar"],
        "Kolkata": ["Kolkata", "Salt Lake", "Howrah", "New Town"],
        "Pune": ["Pune", "Hinjewadi", "Kothrud", "Baner"]
    }
    return nearby.get(location, [location])
# print(get_nearby_locations("Indiranagar"))

# doctors = [{"name": "Dr. Ramesh", "specialization": "Endocrinologist", "location": "Gajuwaka"},
#  {"name": "Dr. Priya", "specialization": "General Physician", "location": "Visakhapatnam"},
#  {"name": "Dr. Anil", "specialization": "Pulmonologist", "location": "NAD Junction"},
#  {"name": "Dr. Sneha", "specialization": "Dermatologist", "location": "Gajuwaka"},
#  {"name": "Dr. Kiran", "specialization": "Dentist", "location": "Visakhapatnam"}]

DISEASE_SPECIALIST_MAP = {"diabetes": "Endocrinologist",
 "thyroid disorder": "Endocrinologist",
 "high blood pressure": "Cardiologist",
 "chest pain": "Cardiologist",
 "heart palpitations": "Cardiologist",
 "fever": "General Physician",
    "common cold": "General Physician",
    "body weakness": "General Physician",
    "migraine": "Neurologist",
    "seizures": "Neurologist",
    "memory loss": "Neurologist",
    "asthma": "Pulmonologist",
    "shortness of breath": "Pulmonologist",
    "chronic cough": "Pulmonologist",
    "skin rash": "Dermatologist",
    "acne": "Dermatologist",
    "eczema": "Dermatologist",
    "tooth pain": "Dentist",
    "cavity": "Dentist",
    "gum bleeding": "Dentist",
    "eye pain": "Ophthalmologist",
    "blurred vision": "Ophthalmologist",
    "cataract": "Ophthalmologist",
    "knee pain": "Orthopedic Surgeon",
    "back pain": "Orthopedic Surgeon",
    "fracture": "Orthopedic Surgeon",
    "pregnancy care": "Gynecologist",
    "menstrual problems": "Gynecologist",
    "fertility issues": "Gynecologist",
    "kidney stone": "Urologist",
    "urine infection": "Urologist",
    "prostate problem": "Urologist",
    "stomach pain": "Gastroenterologist",
    "gastric issues": "Gastroenterologist",
    "liver disease": "Gastroenterologist",
    "depression": "Psychiatrist",
    "anxiety": "Psychiatrist",
    "sleep disorder": "Psychiatrist",
    "child vaccination": "Pediatrician",
    "child fever": "Pediatrician",
    "growth issues": "Pediatrician",
    "hearing loss": "ENT Specialist",
    "ear infection": "ENT Specialist",
    "tonsillitis": "ENT Specialist",
    "joint swelling": "Rheumatologist",
    "arthritis": "Rheumatologist",
    "autoimmune disease": "Rheumatologist",
    "cancer screening": "Oncologist",
    "tumor treatment": "Oncologist",
    "chemotherapy": "Oncologist",
    "allergy": "Allergist",
    "food allergy": "Allergist",
    "seasonal allergy": "Allergist",
    "weight management": "Dietitian",
    "nutrition deficiency": "Dietitian",
    "obesity": "Dietitian",
    "stroke recovery": "Neurologist",
    "paralysis": "Neurologist",
    "thyroid swelling": "Endocrinologist",
    "sinus infection": "ENT Specialist",
    "varicose veins": "Vascular Surgeon",
    "blood clot": "Hematologist",
    "anemia": "Hematologist",
    "diarrhea": "Gastroenterologist",
    "constipation": "Gastroenterologist",
    "piles": "Proctologist",
    "hernia": "General Surgeon",
    "appendicitis": "General Surgeon",
    "burn injury": "Plastic Surgeon",
    "cosmetic surgery": "Plastic Surgeon",
    "infertility": "Gynecologist",
    "hepatitis": "Gastroenterologist",
    }

SPECIALIST_SET = set(DISEASE_SPECIALIST_MAP.values())
def map_disease_to_specialist(disease: str)->str:
    """
    Maps user input (either layman disease or specialist name) 
    to a valid specialist mapping.
    Returns formatted string like 'Fever - General Physician'.
    """
    term = disease.lower().strip()
    # Case 1: Input is a layman disease
    if term in DISEASE_SPECIALIST_MAP:
        specialist = DISEASE_SPECIALIST_MAP[term]
        return f"{term.title()} - {specialist}"
    # Case 2: Input is already a specialist
    for spec in SPECIALIST_SET:
        if term == spec.lower():
            return f"{spec} - {spec}"
    # Default fallback
    return f"{term.title()} - General Physician"

# print(map_disease_to_specialist('Skin Rash'))