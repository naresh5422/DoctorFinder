import os
import json
import random
from sentence_transformers import SentenceTransformer, util
import spacy
import numpy as np
from app.extension import db
from app.models import Doctor

# --- AI Model Loading ---
# In a production Flask app, this should be initialized once when the app starts,
# for example, within your Flask app factory, to avoid reloading on every request.
try:
    nlp_ner = spacy.load("en_core_web_sm")
    semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
    AI_MODELS_LOADED = True
    print("AI models loaded successfully.")
except (OSError, ImportError) as e:
    nlp_ner = None
    semantic_model = None
    AI_MODELS_LOADED = False
    print(f"Warning: Could not load AI models. Semantic search will be disabled. Error: {e}")
    print("To enable, run: pip install sentence-transformers spacy torch")
    print("And then: python -m spacy download en_core_web_sm")


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
    # NOTE: Hospital services are randomly generated as they are not stored in the database.
    hospital_services = [
        "24/7 Emergency Care", "ICU", "Cardiology", "Neurology", "Orthopedics",
        "Oncology", "Pediatrics", "Gynecology", "Radiology", "Pharmacy",
        "Ambulance Service", "General Surgery", "Diagnostics Lab"
    ]

    # This function now reads from the database to ensure data consistency.
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

# --- Location Data ---
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

# NEW: Create a reverse map to find the canonical city from any of its sub-locations.
# e.g., {"gachibowli": "Hyderabad", "secunderabad": "Hyderabad"}
REVERSE_NEARBY_MAP = {
    sub_loc.lower(): canonical_key
    for canonical_key, sub_loc_list in NEARBY_LOCATIONS_MAP.items()
    for sub_loc in sub_loc_list
}

# NEW: Add a map for common location abbreviations and alternate spellings.
LOCATION_ALIASES = {
    # Canonical Name: [list of aliases]
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
# Create a reverse map for quick lookup: {alias: canonical_name}
REVERSE_ALIAS_MAP = {
    alias.lower(): canonical 
    for canonical, aliases in LOCATION_ALIASES.items() 
    for alias in aliases
}
SORTED_ALIASES = sorted(REVERSE_ALIAS_MAP.keys(), key=len, reverse=True)

# Create a flat, lowercased list of all known locations for efficient searching.
# Sorted by length descending to match longer names first (e.g., "Electronic City" before "City").
ALL_KNOWN_LOCATIONS = sorted(
    list(set([loc.lower() for sublist in NEARBY_LOCATIONS_MAP.values() for loc in sublist])),
    key=len,
    reverse=True
)

def get_nearby_locations(location):
    """
    Finds a list of nearby/related locations for a given location.
    It can find the main city from a sub-location and return all related areas.
    The lookup is case-insensitive and resolves common aliases.
    """
    if not location:
        return []

    original_input_title = location.strip().title()
    search_term = location.strip().lower()

    # 1. Resolve alias first (e.g., 'hyd' -> 'Hyderabad')
    canonical_from_alias = REVERSE_ALIAS_MAP.get(search_term)
    if canonical_from_alias:
        search_term = canonical_from_alias.lower() # Use the resolved canonical name for further lookups

    # 2. Look up the term in the reverse map to find the main group key.
    main_group_key = REVERSE_NEARBY_MAP.get(search_term)
    if main_group_key:
        return NEARBY_LOCATIONS_MAP.get(main_group_key)

    # 3. Fallback: Check if the original input (or its alias) is a key in the main map.
    key_to_check = canonical_from_alias if canonical_from_alias else original_input_title
    return NEARBY_LOCATIONS_MAP.get(key_to_check, [original_input_title])

DISEASE_SPECIALIST_MAP = {"diabetes": "Endocrinologist",
 "sugar": "Endocrinologist",
 "thyroid disorder": "Endocrinologist",
 "high blood pressure": "Cardiologist",
 "bp": "Cardiologist",
 "chest pain": "Cardiologist",
 "heart pain": "Cardiologist",
 "heart palpitations": "Cardiologist",
 "fever": "General Physician",
    "common cold": "General Physician",
    "headache": "Neurologist",
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
    "toothache": "Dentist",
    "cavity": "Dentist",
    "gum bleeding": "Dentist",
    "eye pain": "Ophthalmologist",
    "blurred vision": "Ophthalmologist",
    "cataract": "Ophthalmologist",
    "knee pain": "Orthopedic Surgeon",
    "back pain": "Orthopedic Surgeon",
    "fracture": "Orthopedic Surgeon",
    "neck pain": "Orthopedic Surgeon",
    "pregnancy care": "Gynecologist",
    "menstrual problems": "Gynecologist",
    "fertility issues": "Gynecologist",
    "kidney stone": "Urologist",
    "urine infection": "Urologist",
    "prostate problem": "Urologist",
    "stomach pain": "Gastroenterologist",
    "stomach ache": "Gastroenterologist",
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
    "sore throat": "ENT Specialist",
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
LOWERCASE_SPECIALIST_MAP = {spec.lower(): spec for spec in SPECIALIST_SET}
DISEASE_EMBEDDINGS = {}

# --- Pre-compute embeddings for semantic search (at startup) ---
if AI_MODELS_LOADED:
    try:
        # Get a unique list of diseases/symptoms from our map
        disease_list = list(DISEASE_SPECIALIST_MAP.keys())
        # Compute embeddings for all of them
        disease_embeddings_tensor = semantic_model.encode(disease_list, convert_to_tensor=True)
        DISEASE_EMBEDDINGS = {
            "diseases": disease_list,
            "embeddings": disease_embeddings_tensor
        }
    except Exception as e:
        print(f"Error pre-computing embeddings: {e}")
        AI_MODELS_LOADED = False

# --- Autocomplete Suggestion Generation ---
# Pre-compile a list of all possible search terms for fast autocompletion.
AUTOCOMPLETE_TERMS = set()
AUTOCOMPLETE_TERMS.update([d.title() for d in DISEASE_SPECIALIST_MAP.keys()])
AUTOCOMPLETE_TERMS.update([s.title() for s in SPECIALIST_SET])
AUTOCOMPLETE_TERMS.update([loc.title() for loc in ALL_KNOWN_LOCATIONS])
AUTOCOMPLETE_TERMS.update(list(REVERSE_ALIAS_MAP.keys()))
# Add a specific term to guide users to emergency services.
AUTOCOMPLETE_TERMS.add("Emergency Services")

SORTED_AUTOCOMPLETE_TERMS = sorted(list(AUTOCOMPLETE_TERMS))

def get_autocomplete_suggestions(query: str, limit: int = 10):
    """
    Provides autocomplete suggestions based on a partial query.
    Searches against a pre-compiled list of diseases, specialties, and locations.
    Prioritizes suggestions that start with the query.
    """
    if not query:
        return []
    
    query_lower = query.lower()
    
    # 1. Find matches that start with the query (highest priority)
    starts_with_matches = [
        term for term in SORTED_AUTOCOMPLETE_TERMS if term.lower().startswith(query_lower)
    ]
    
    # If we have enough matches, return them.
    if len(starts_with_matches) >= limit:
        return starts_with_matches[:limit]
    
    # 2. Find matches that contain the query string, but don't start with it.
    contains_matches = [
        term for term in SORTED_AUTOCOMPLETE_TERMS 
        if query_lower in term.lower() and term not in starts_with_matches
    ]
    
    # Combine the lists and return up to the limit.
    all_matches = starts_with_matches + contains_matches
    return all_matches[:limit]


# --- Location-specific Autocomplete ---
# Combine all known locations and their aliases into one list for suggestions.
ALL_LOCATION_TERMS = set([loc.title() for loc in ALL_KNOWN_LOCATIONS])
ALL_LOCATION_TERMS.update([alias for alias in REVERSE_ALIAS_MAP.keys()])
# Ensure canonical names from aliases are also present, title-cased
ALL_LOCATION_TERMS.update([name.title() for name in LOCATION_ALIASES.keys()])
SORTED_LOCATION_TERMS = sorted(list(ALL_LOCATION_TERMS))

def get_location_suggestions(query: str, limit: int = 10):
    """
    Provides autocomplete suggestions for locations only.
    Searches against a pre-compiled list of locations and their aliases.
    """
    if not query:
        return []
    
    query_lower = query.lower()
    
    # 1. Find matches that start with the query (highest priority)
    starts_with_matches = [
        term for term in SORTED_LOCATION_TERMS if term.lower().startswith(query_lower)
    ]
    
    # If we have enough matches, return them.
    if len(starts_with_matches) >= limit:
        return starts_with_matches[:limit]
    
    # 2. Find matches that contain the query string, but don't start with it.
    contains_matches = [
        term for term in SORTED_LOCATION_TERMS 
        if query_lower in term.lower() and term not in starts_with_matches
    ]
    
    # Combine the lists and return up to the limit.
    all_matches = starts_with_matches + contains_matches
    return all_matches[:limit]

def map_disease_to_specialist(disease: str)->str:
    """
    Maps user input to a specialist. Returns a dictionary with the original term,
    the mapped specialist, and a 'did_you_mean' suggestion if applicable.
    """
    term = disease.lower().strip()

    # --- AI-powered Semantic Search (if models are loaded) ---
    if AI_MODELS_LOADED and DISEASE_EMBEDDINGS and term:
        try:
            query_embedding = semantic_model.encode(term, convert_to_tensor=True)
            cosine_scores = util.cos_sim(query_embedding, DISEASE_EMBEDDINGS["embeddings"])[0]
            best_match_index = np.argmax(cosine_scores)
            best_match_score = cosine_scores[best_match_index]
            
            # Lowered threshold to be more forgiving of typos.
            if best_match_score > 0.45:
                matched_disease = DISEASE_EMBEDDINGS["diseases"][best_match_index]
                specialist = DISEASE_SPECIALIST_MAP[matched_disease]
                
                # Provide a "did you mean" suggestion for medium-confidence matches.
                did_you_mean = None
                if best_match_score < 0.9 and term != matched_disease:
                    did_you_mean = matched_disease.title()

                return {
                    "original_term": term.title(),
                    "specialist": specialist,
                    "did_you_mean": did_you_mean
                }
        except Exception as e:
            print(f"Semantic search failed: {e}")
            # Fall through to keyword search if AI fails

    # --- Fallback to existing keyword-based search ---
    if term in DISEASE_SPECIALIST_MAP:
        specialist = DISEASE_SPECIALIST_MAP[term]
        return {"original_term": term.title(), "specialist": specialist, "did_you_mean": None}
    if term in LOWERCASE_SPECIALIST_MAP:
        specialist = LOWERCASE_SPECIALIST_MAP[term]
        return {"original_term": specialist, "specialist": specialist, "did_you_mean": None}

    # If no match is found, return None for the specialist.
    return {"original_term": term.title(), "specialist": None, "did_you_mean": None}

def extract_entities_from_query(query: str) -> dict:
    """
    Uses a combination of NER and custom keyword search to extract one or more locations
    and treats the rest of the query as the symptom/disease.
    Example: "skin doctor in Gachibowli and Tirupati" -> {'symptom': 'skin doctor', 'locations': ['Gachibowli', 'Tirupati']}
    """
    if not AI_MODELS_LOADED or not nlp_ner:
        return {'symptom': query, 'locations': []}

    import re
    symptom_text = query
    locations = []

    # 1. Use spaCy's NER to find all GPEs (Geopolitical Entities)
    doc = nlp_ner(query)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            locations.append(ent.text.title())
            symptom_text = symptom_text.replace(ent.text, "")

    # 2. Use custom search for our specific known locations and aliases.
    # This is more precise and catches terms spaCy might miss (e.g., 'Gachibowli', 'hyd').
    all_searchable_terms = sorted(ALL_KNOWN_LOCATIONS + SORTED_ALIASES, key=len, reverse=True)
    
    for term in all_searchable_terms:
        pattern = r'\b' + re.escape(term) + r'\b'
        matches = list(re.finditer(pattern, symptom_text, re.IGNORECASE))
        if matches:
            for match in matches:
                found_term = match.group(0).lower()
                # Resolve alias or title case the location
                canonical_location = REVERSE_ALIAS_MAP.get(found_term, found_term.title())
                if canonical_location not in locations:
                    locations.append(canonical_location)
            # Remove from the text so we don't match sub-parts
            symptom_text = re.sub(pattern, '', symptom_text, flags=re.IGNORECASE)

    # 3. Clean up the remaining text to get the core symptom.
    doc_symptom = nlp_ner(symptom_text)
    symptom_words = [
        token.text for token in doc_symptom 
        if not token.is_stop and not token.is_punct and token.text.lower() not in ['doctor', 'doctors', 'dr', 'in', 'at', 'near', 'for', 'my', 'i', 'have', 'need', 'and', 'or', ',']
    ]
    symptom_text = " ".join(symptom_words).strip()
    symptom_text = re.sub(r'\s+', ' ', symptom_text).strip() # Remove extra spaces
    
    if locations and not symptom_text:
        final_symptom = ""
    else:
        final_symptom = symptom_text if symptom_text else query
    
    # Return a unique list of found locations, preserving order
    unique_locations = list(dict.fromkeys(locations))
    return {'symptom': final_symptom, 'locations': unique_locations}