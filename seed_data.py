import os
from app.main import create_app
from app.models import Specialty, Symptom, Location, LocationAlias
from app.extension import db
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Data from doctor_service.py ---
NEARBY_LOCATIONS_MAP = {
    "Gajuwaka": ["Gajuwaka", "Visakhapatnam", "NAD Junction", "Malkapuram"],
    "Hyderabad": ["Hyderabad", "Secunderabad", "Gachibowli", "Madhapur", "Kukatpally"],
    "Tirupati": ["Tirupati", "Renigunta", "Chandragiri", "Mangalam"],
    "Chennai": ["Chennai", "Velachery", "Tambaram", "T Nagar"],
    "Bangalore": ["Bangalore", "Bengaluru", "Whitefield", "Electronic City", "Indiranagar", "HSR Layout"],
    "Vijayawada": ["Vijayawada", "Benz Circle", "Governorpet", "Gollapudi"],
    "Delhi": ["Delhi", "Dwarka", "Saket", "Karol Bagh"],
    "Mumbai": ["Mumbai", "Andheri", "Bandra", "Dadar"],
    "Kolkata": ["Kolkata", "Salt Lake", "Howrah", "New Town"],
    "Pune": ["Pune", "Hinjewadi", "Kothrud", "Baner"]
}
LOCATION_ALIASES = {
    "Hyderabad": ["hyd"],
    "Visakhapatnam": ["vizag", "vskp"],
    "Bangalore": ["ben", "ban", "bang", "bengalore", "bangaluru"],
    "Delhi": ["del"],
    "Mumbai": ["mum", "bom"],
    "Kolkata": ["kol", "ccu"],
    "Chennai": ["che", "maa"],
    "Pune": ["pun"],
    "Secunderabad": ["sec"],
}
DISEASE_SPECIALIST_MAP = {
    "diabetes": "Endocrinologist", "sugar": "Endocrinologist", "thyroid disorder": "Endocrinologist",
    "high blood pressure": "Cardiologist", "bp": "Cardiologist", "chest pain": "Cardiologist",
    "heart pain": "Cardiologist", "heart palpitations": "Cardiologist", "fever": "General Physician",
    "common cold": "General Physician", "headache": "Neurologist", "body weakness": "General Physician",
    "migraine": "Neurologist", "seizures": "Neurologist", "memory loss": "Neurologist",
    "asthma": "Pulmonologist", "shortness of breath": "Pulmonologist", "chronic cough": "Pulmonologist",
    "skin rash": "Dermatologist", "acne": "Dermatologist", "eczema": "Dermatologist",
    "tooth pain": "Dentist", "toothache": "Dentist", "cavity": "Dentist", "gum bleeding": "Dentist",
    "eye pain": "Ophthalmologist", "blurred vision": "Ophthalmologist", "cataract": "Ophthalmologist",
    "knee pain": "Orthopedic Surgeon", "back pain": "Orthopedic Surgeon", "fracture": "Orthopedic Surgeon",
    "neck pain": "Orthopedic Surgeon", "pregnancy care": "Gynecologist", "menstrual problems": "Gynecologist",
    "fertility issues": "Gynecologist", "kidney stone": "Urologist", "urine infection": "Urologist",
    "prostate problem": "Urologist", "stomach pain": "Gastroenterologist", "stomach ache": "Gastroenterologist",
    "gastric issues": "Gastroenterologist", "liver disease": "Gastroenterologist", "depression": "Psychiatrist",
    "anxiety": "Psychiatrist", "sleep disorder": "Psychiatrist", "child vaccination": "Pediatrician",
    "child fever": "Pediatrician", "growth issues": "Pediatrician", "hearing loss": "ENT Specialist",
    "ear infection": "ENT Specialist", "sore throat": "ENT Specialist", "tonsillitis": "ENT Specialist",
    "joint swelling": "Rheumatologist", "arthritis": "Rheumatologist", "autoimmune disease": "Rheumatologist",
    "cancer screening": "Oncologist", "tumor treatment": "Oncologist", "chemotherapy": "Oncologist",
    "allergy": "Allergist", "food allergy": "Allergist", "seasonal allergy": "Allergist",
    "weight management": "Dietitian", "nutrition deficiency": "Dietitian", "obesity": "Dietitian",
    "stroke recovery": "Neurologist", "paralysis": "Neurologist", "thyroid swelling": "Endocrinologist",
    "sinus infection": "ENT Specialist", "varicose veins": "Vascular Surgeon", "blood clot": "Hematologist",
    "anemia": "Hematologist", "diarrhea": "Gastroenterologist", "constipation": "Gastroenterologist",
    "piles": "Proctologist", "hernia": "General Surgeon", "appendicitis": "General Surgeon",
    "burn injury": "Plastic Surgeon", "cosmetic surgery": "Plastic Surgeon", "infertility": "Gynecologist",
    "hepatitis": "Gastroenterologist",
}

def seed_specialties_and_symptoms():
    """Seeds specialties and symptoms from the hardcoded map."""
    print("Seeding specialties and symptoms...")
    specialty_names = set(DISEASE_SPECIALIST_MAP.values())
    specialty_map = {}

    for name in specialty_names:
        specialty = Specialty.query.filter_by(name=name).first()
        if not specialty:
            specialty = Specialty(name=name)
            db.session.add(specialty)
            print(f"  - Added specialty: {name}")
        specialty_map[name] = specialty
    
    db.session.commit() # Commit specialties to get their IDs

    for symptom_name, specialty_name in DISEASE_SPECIALIST_MAP.items():
        symptom = Symptom.query.filter_by(name=symptom_name).first()
        if not symptom:
            specialty = specialty_map[specialty_name]
            symptom = Symptom(name=symptom_name, specialty_id=specialty.id)
            db.session.add(symptom)
            print(f"  - Added symptom: '{symptom_name}' -> {specialty_name}")
    
    db.session.commit()
    print("...done seeding specialties and symptoms.")

def seed_locations_and_aliases():
    """Seeds locations and aliases from hardcoded maps."""
    print("Seeding locations and aliases...")
    location_map = {}

    # First pass: create all locations
    all_location_names = set()
    for parent, children in NEARBY_LOCATIONS_MAP.items():
        all_location_names.add(parent)
        for child in children:
            all_location_names.add(child)

    for name in all_location_names:
        location = Location.query.filter_by(name=name).first()
        if not location:
            location = Location(name=name)
            db.session.add(location)
            print(f"  - Added location: {name}")
        location_map[name] = location
    
    db.session.commit() # Commit to get IDs

    # Second pass: set parent-child relationships
    for parent_name, children_names in NEARBY_LOCATIONS_MAP.items():
        parent_loc = location_map[parent_name]
        for child_name in children_names:
            if child_name != parent_name:
                child_loc = location_map[child_name]
                if child_loc.parent_id is None:
                    child_loc.parent_id = parent_loc.id
                    print(f"  - Set parent for '{child_name}' -> '{parent_name}'")

    # Third pass: add aliases
    for canonical_name, aliases in LOCATION_ALIASES.items():
        location = Location.query.filter_by(name=canonical_name).first()
        if location:
            for alias_name in aliases:
                alias = LocationAlias.query.filter_by(alias=alias_name).first()
                if not alias:
                    alias = LocationAlias(alias=alias_name, location_id=location.id)
                    db.session.add(alias)
                    print(f"  - Added alias: '{alias_name}' -> '{canonical_name}'")
    
    db.session.commit()
    print("...done seeding locations and aliases.")


def seed_all():
    """
    Main function to run all seeding operations.
    This is idempotent and can be run multiple times safely.
    """
    app = create_app()
    with app.app_context():
        seed_specialties_and_symptoms()
        seed_locations_and_aliases()
        print("\n✅ Data seeding complete.")

if __name__ == '__main__':
    seed_all()