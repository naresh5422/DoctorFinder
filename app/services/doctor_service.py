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

# doctors = [{"name": "Dr. Ramesh", "specialization": "Endocrinologist", "location": "Gajuwaka"},
#  {"name": "Dr. Priya", "specialization": "General Physician", "location": "Visakhapatnam"},
#  {"name": "Dr. Anil", "specialization": "Pulmonologist", "location": "NAD Junction"},
#  {"name": "Dr. Sneha", "specialization": "Dermatologist", "location": "Gajuwaka"},
#  {"name": "Dr. Kiran", "specialization": "Dentist", "location": "Visakhapatnam"}]


def map_disease_to_specialist(disease):
    mapping = {
    "diabetes": "Endocrinologist", 
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
    return mapping.get(disease.lower())

