import os
import json
import random
from sentence_transformers import SentenceTransformer, util
import spacy
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import numpy as np
from app.extension import db
from app.models import Doctor, Specialty, Symptom, Location, LocationAlias
import re

# --- AI Model & Data Caching ---
# These are populated at startup by load_service_data() in main.py to avoid repeated DB queries.
nlp_ner = None
semantic_model = None
AI_MODELS_LOADED = False
SEMANTIC_DATA = {}
AUTOCOMPLETE_DATA = {"all": [], "locations": []}

def load_service_data():
    """
    Loads AI models and data from the database into memory at application start.
    This is a one-time operation called from the app factory.
    """
    global AI_MODELS_LOADED, SEMANTIC_DATA, AUTOCOMPLETE_DATA, nlp_ner, semantic_model
    
    try:
        nlp_ner = spacy.load("en_core_web_sm")
        semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
        AI_MODELS_LOADED = True
        print("✅ AI models (spaCy, SentenceTransformer) loaded successfully.")
    except (OSError, ImportError) as e:
        # --- BEGIN IMPROVEMENT: More helpful error message for missing spaCy model ---
        error_message = str(e)
        print(f"⚠️ Warning: Could not load AI models. Semantic search will be disabled. Error: {error_message}")
        if "[E050]" in error_message or "[E0550]" in error_message: # Common spaCy model-not-found error codes.
            print("   -> FIX: The spaCy NLP model ('en_core_web_sm') is missing. Run this command in your terminal:")
            print("   -> python -m spacy download en_core_web_sm")
        # --- END IMPROVEMENT ---
        return

    # Pre-compute embeddings for semantic search
    try:
        symptoms = Symptom.query.options(joinedload(Symptom.specialty)).all()
        if not symptoms:
            print("⚠️ Warning: No symptoms found in the database. Semantic search will be limited. Run seed_data.py.")
        else:
            symptom_names = [s.name for s in symptoms]
            symptom_embeddings = semantic_model.encode(symptom_names, convert_to_tensor=True)
            SEMANTIC_DATA = {
                "symptoms": symptom_names,
                "embeddings": symptom_embeddings,
                "symptom_to_specialty": {s.name: s.specialty.name for s in symptoms}
            }
            print("✅ Symptom embeddings computed and cached for semantic search.")
    except Exception as e:
        print(f"❌ Error pre-computing embeddings: {e}. Semantic search may not work correctly.")
        AI_MODELS_LOADED = False

    # Pre-compile autocomplete terms
    try:
        symptoms = [s.name.title() for s in Symptom.query.all()]
        specialties = [s.name.title() for s in Specialty.query.all()]
        locations = [l.name.title() for l in Location.query.all()]
        aliases = [a.alias for a in LocationAlias.query.all()]

        all_terms = set(symptoms + specialties + locations + aliases)
        all_terms.add("Emergency Services")
        AUTOCOMPLETE_DATA["all"] = sorted(list(all_terms))

        location_terms = set(locations + aliases)
        AUTOCOMPLETE_DATA["locations"] = sorted(list(location_terms))
        print("✅ Autocomplete suggestions cached from database.")
    except Exception as e:
        print(f"❌ Error caching autocomplete data: {e}. Autocomplete may not work.")


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

def get_nearby_locations(location):
    """
    Finds a list of nearby/related locations for a given location by querying the database.
    It resolves aliases (e.g., 'hyd' -> 'Hyderabad') and finds parent/child relationships.
    """
    if not location:
        return []

    search_term = location.strip().lower()

    # 1. Check for an exact location match
    loc = Location.query.filter(func.lower(Location.name) == search_term).first()

    # 2. If no match, check aliases
    if not loc:
        alias = LocationAlias.query.options(joinedload(LocationAlias.location)).filter(func.lower(LocationAlias.alias) == search_term).first()
        if alias:
            loc = alias.location

    # 3. If a location is found, determine the search group
    if loc:
        # If the location has a parent, the group is the parent and all its children
        if loc.parent:
            parent_loc = loc.parent
            related_locations = [parent_loc.name] + [child.name for child in parent_loc.sub_locations]
            return list(set(related_locations))
        # If the location has no parent, it is a parent itself. The group is the location and its children.
        else:
            related_locations = [loc.name] + [child.name for child in loc.sub_locations]
            return list(set(related_locations))

    # 4. Fallback: if no match, return the original input as a single-item list
    return [location.strip().title()]

def get_autocomplete_suggestions(query: str, limit: int = 10):
    """
    Provides autocomplete suggestions based on a partial query.
    Searches against a pre-compiled list of diseases, specialties, and locations.
    Prioritizes suggestions that start with the query.
    """
    if not query:
        return []
    
    query_lower = query.lower()
    
    # Use the cached list from AUTOCOMPLETE_DATA
    suggestion_pool = AUTOCOMPLETE_DATA.get("all", [])
    if not suggestion_pool:
        return []

    # 1. Find matches that start with the query (highest priority)
    starts_with_matches = [term for term in suggestion_pool if term.lower().startswith(query_lower)]
    
    # If we have enough matches, return them.
    if len(starts_with_matches) >= limit:
        return starts_with_matches[:limit]
    
    # 2. Find matches that contain the query string, but don't start with it.
    contains_matches = [term for term in suggestion_pool if query_lower in term.lower() and term not in starts_with_matches]
    
    # Combine the lists and return up to the limit.
    all_matches = starts_with_matches + contains_matches
    return all_matches[:limit]

def get_location_suggestions(query: str, limit: int = 10):
    """
    Provides autocomplete suggestions for locations only.
    Searches against a pre-compiled list of locations and their aliases.
    """
    if not query:
        return []
    
    query_lower = query.lower()

    # Use the cached list from AUTOCOMPLETE_DATA
    suggestion_pool = AUTOCOMPLETE_DATA.get("locations", [])
    if not suggestion_pool:
        return []

    # 1. Find matches that start with the query (highest priority)
    starts_with_matches = [term for term in suggestion_pool if term.lower().startswith(query_lower)]
    
    # If we have enough matches, return them.
    if len(starts_with_matches) >= limit:
        return starts_with_matches[:limit]
    
    # 2. Find matches that contain the query string, but don't start with it.
    contains_matches = [term for term in suggestion_pool if query_lower in term.lower() and term not in starts_with_matches]
    
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
    if AI_MODELS_LOADED and SEMANTIC_DATA and term:
        try:
            query_embedding = semantic_model.encode(term, convert_to_tensor=True)
            cosine_scores = util.cos_sim(query_embedding, SEMANTIC_DATA["embeddings"])[0]
            best_match_index = np.argmax(cosine_scores)
            best_match_score = cosine_scores[best_match_index]
            
            # Lowered threshold to be more forgiving of typos.
            if best_match_score > 0.45:
                matched_disease = SEMANTIC_DATA["symptoms"][best_match_index]
                specialist = SEMANTIC_DATA["symptom_to_specialty"][matched_disease]
                
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
    # Check for exact symptom match
    symptom = Symptom.query.options(joinedload(Symptom.specialty)).filter(func.lower(Symptom.name) == term).first()
    if symptom:
        return {"original_term": term.title(), "specialist": symptom.specialty.name, "did_you_mean": None}

    # Check for exact specialty match
    specialty = Specialty.query.filter(func.lower(Specialty.name) == term).first()
    if specialty:
        return {"original_term": specialty.name, "specialist": specialty.name, "did_you_mean": None}

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

    symptom_text = query
    locations = []

    # 1. Use spaCy's NER to find all GPEs (Geopolitical Entities)
    doc = nlp_ner(query)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]: # GPE (Geopolitical Entity) and LOC (Location)
            locations.append(ent.text.title())
            symptom_text = symptom_text.replace(ent.text, "")

    # 2. Use custom search for our specific known locations and aliases.
    # This is more precise and catches terms spaCy might miss (e.g., 'Gachibowli', 'hyd').
    all_searchable_terms = sorted(AUTOCOMPLETE_DATA.get("locations", []), key=len, reverse=True)
    
    for term in all_searchable_terms:
        pattern = r'\b' + re.escape(term) + r'\b'
        matches = list(re.finditer(pattern, symptom_text, re.IGNORECASE))
        if matches:
            for match in matches:
                # Find the canonical location from the DB to add to the list
                nearby = get_nearby_locations(match.group(0)) # This resolves aliases
                canonical_location = nearby[0] if nearby else match.group(0).title()
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