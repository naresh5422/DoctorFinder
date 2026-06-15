from flask import render_template, request, session, redirect, url_for, flash, jsonify, current_app
from app.services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist, find_hospitals, get_featured_hospitals, extract_entities_from_query, get_autocomplete_suggestions, get_location_suggestions
from app.services.pinecone_rag import generate_rag_answer
from app.services.rag_pipeline.answering import format_user_rag_response
import os
import random
import re
from werkzeug.utils import secure_filename
from app.extension import db, mail, login_required, check_gmail_app_password
from app.models import SearchHistory, Patient, Doctor, Appointment, Review, Message
from datetime import datetime, date
from sqlalchemy import func, case, and_
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_mail import Message as MailMessage  # Alias to avoid name conflict with model
from firebase_admin import auth
from twilio.rest import Client
from twilio.base import exceptions
import smtplib
from markupsafe import Markup


CHATBOT_FAQS = {
    "how do i book an appointment": {
        "reply": "Search by symptom, specialty, or location. Open a doctor profile, choose an available online or in-person slot, and submit the booking request. If you are not logged in, CareSlotly will ask you to login before booking.",
        "actions": [
            ("Find doctors", "browse_doctors", "primary"),
            ("Login", "login", "secondary"),
        ],
    },
    "can i consult online": {
        "reply": "Yes. Doctors who support online consultations show an Online badge and online slots. Choose an online slot while booking if it is available.",
        "actions": [
            ("Browse doctors", "browse_doctors", "primary"),
        ],
    },
    "how do i find the right specialist": {
        "reply": "Tell me your symptom or condition, such as 'chest pain', 'skin rash', or 'tooth pain'. I will map it to a suitable specialty and help you open matching doctors.",
        "actions": [
            ("Browse doctors", "browse_doctors", "primary"),
        ],
    },
    "how do i message my doctor": {
        "reply": "Patient-doctor messaging is available after you book an appointment. It may also remain open during the follow-up period after a completed appointment.",
        "actions": [
            ("My messages", "list_conversations", "primary"),
            ("My appointments", "my_appointments", "secondary"),
        ],
    },
}

CHATBOT_HEALTH_ADVICE = {
    "back pain": {
        "reply": (
            "For back pain, try gentle stretching, maintain good posture, use a warm compress, and keep moving with short walks. "
            "If pain is severe, lasts more than a few days, or causes numbness or weakness, consult an orthopedic or physiotherapy specialist."
        ),
    },
    "headache": {
        "reply": (
            "For a headache, rest in a quiet, dark room, stay hydrated, and avoid bright screens. "
            "If it is sudden, very severe, or accompanied by vision changes or weakness, seek medical help."
        ),
    },
    "migraine": {
        "reply": (
            "For migraine, rest in a quiet, dark room, stay hydrated, and avoid strong smells or loud noise. "
            "If the pain is severe or accompanied by visual changes, seek medical help."
        ),
    },
    "fever": {
        "reply": (
            "For fever, drink plenty of fluids, rest, and use a cool compress or paracetamol if needed. "
            "If the fever stays high for more than two days or you have other worrying symptoms, see a doctor."
        ),
    },
    "cold": {
        "reply": (
            "For a common cold, rest, drink warm fluids, use saline nasal drops, and keep your environment humidified. "
            "If symptoms last longer than a week or worsen, consult a doctor."
        ),
    },
    "cough": {
        "reply": (
            "For a cough, stay hydrated, inhale steam, and avoid smoke or dusty air. "
            "If it is persistent, produces blood, or comes with high fever, book a doctor consultation."
        ),
    },
    "sore throat": {
        "reply": (
            "For a sore throat, drink warm fluids, gargle with salt water, and rest your voice. "
            "If it is severe, lasts more than a few days, or comes with fever, see a doctor."
        ),
    },
    "stomach pain": {
        "reply": (
            "For mild stomach pain, rest, eat light, bland foods, and avoid spicy or greasy meals. "
            "If pain is severe, persistent, or accompanied by vomiting or blood, seek medical attention."
        ),
    },
    "diarrhea": {
        "reply": (
            "For diarrhea, drink plenty of fluids, use oral rehydration solutions, and eat light, easy-to-digest foods. "
            "If diarrhea continues for more than a day, contains blood, or causes dehydration, see a doctor."
        ),
    },
    "vomiting": {
        "reply": (
            "For vomiting, sip clear fluids slowly, avoid solid foods until it subsides, and rest. "
            "If vomiting is severe, persistent, or you cannot keep fluids down, get medical care."
        ),
    },
    "joint pain": {
        "reply": (
            "For joint pain, apply ice or heat, rest the joint, and avoid heavy lifting. "
            "If the pain is sudden, swelling appears, or it limits movement, consult an orthopedist or rheumatologist."
        ),
    },
    "allergy": {
        "reply": (
            "For mild allergy symptoms, avoid the trigger, rinse your nose with saline, and take an antihistamine if needed. "
            "If you have breathing difficulty, swelling, or a rash spreading fast, seek urgent medical help."
        ),
    },
    "acidity": {
        "reply": (
            "For acidity, avoid spicy and fatty foods, eat smaller meals, and limit caffeine. "
            "If heartburn is frequent or severe, speak with a doctor for further evaluation."
        ),
    },
    "acne": {
        "reply": (
            "For acne, keep your skin clean, use a gentle cleanser, and avoid squeezing pimples. "
            "If acne is persistent or painful, see a dermatologist for the right treatment."
        ),
    },
    "stress": {
        "reply": (
            "For stress, practice deep breathing, take short breaks, get enough sleep, and stay active. "
            "If stress is overwhelming or affecting your daily life, talk to a doctor or counselor."
        ),
    },
    "fatigue": {
        "reply": (
            "For fatigue, get enough rest, stay hydrated, eat balanced meals, and take short activity breaks. "
            "If fatigue continues despite rest, discuss it with a healthcare provider."
        ),
    },
    "insomnia": {
        "reply": (
            "For insomnia, keep a regular sleep schedule, avoid screens before bed, and create a calm sleep environment. "
            "If poor sleep continues, consult a healthcare provider to rule out underlying causes."
        ),
    },
    "eye irritation": {
        "reply": (
            "For eye irritation, rinse your eyes with clean water, avoid rubbing them, and rest from screens. "
            "If irritation persists, causes pain, or affects vision, see an eye specialist."
        ),
    },
}

def _normalize_chatbot_text(message):
    normalized = re.sub(r"[^a-z0-9\s]", "", message.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _chatbot_health_advice_response(message):
    normalized = _normalize_chatbot_text(message)
    triggers = [
        "remedy", "remedies", "solution", "treatment", "treat", "help for", "help with", "advice for", "what can i do for", "manage", "best way",
    ]
    health_terms = [
        "symptom", "symptoms", "pain", "fever", "cold", "cough", "rash", "headache", "migraine", "acidity",
        "diarrhea", "vomiting", "allergy", "acne", "stress", "fatigue", "insomnia", "irritation", "throat",
        "stomach", "joint", "back", "eye",
    ]
    if not any(trigger in normalized for trigger in triggers) and not any(condition in normalized for condition in CHATBOT_HEALTH_ADVICE):
        return None

    for condition, advice in CHATBOT_HEALTH_ADVICE.items():
        if condition in normalized:
            actions = [
                _chatbot_action("Show doctors", style="primary", message="show doctors list"),
                _chatbot_action("Contact support", style="secondary", message="contact support"),
            ]
            if "patient_id" in session:
                actions.insert(1, _chatbot_action("My appointments", message="show my appointments"))
            return {"reply": advice["reply"], "actions": actions}

    has_health_intent = any(term in normalized for term in health_terms)
    has_health_trigger = any(trigger in normalized for trigger in triggers)
    if has_health_trigger and has_health_intent:
        actions = [
            _chatbot_action("Show doctors", style="primary", message="show doctors list"),
            _chatbot_action("Contact support", style="secondary", message="contact support"),
        ]
        if "patient_id" in session:
            actions.insert(1, _chatbot_action("My appointments", message="show my appointments"))
        return {
            "reply": (
                "I’m not sure about that exact symptom, but you can try rest, hydration, and gentle self-care. "
                "If symptoms persist or worsen, it’s best to consult a doctor so they can provide a proper diagnosis."
            ),
            "actions": actions,
        }

    return None


def _filter_doctor_slots(doctors_list):
    """
    A helper function to filter a list of doctors' available_slots.
    It removes past slots and already booked slots. This version is optimized
    to avoid making a separate database query for each doctor (N+1 problem).
    """
    if not doctors_list:
        return doctors_list

    today = date.today()
    now = datetime.now()

    doctor_ids = [doc.id for doc in doctors_list]
    all_slot_dates = set()
    for doc in doctors_list:
        # Correctly iterate through the new nested structure to get all dates
        if isinstance(doc.available_slots, dict):
            for consult_type in ['online', 'in-person']:
                if isinstance(doc.available_slots.get(consult_type), dict):
                    all_slot_dates.update(doc.available_slots[consult_type].keys())

    # If no doctors have any slots defined, we can just clear them and return.
    if not all_slot_dates:
        for doc in doctors_list:
            doc.available_slots = {}
        return doctors_list

    # --- Optimized Appointment Fetching ---
    # Fetch all relevant appointments for all doctors in the list in a single query.
    all_appointments = Appointment.query.filter(
        Appointment.doctor_id.in_(doctor_ids),
        Appointment.appointment_date.cast(db.Date).in_(list(all_slot_dates)),
        Appointment.status.in_(['Pending', 'Confirmed'])
    ).all()

    # Create a lookup map for booked slots: {doctor_id: {booked_slot_key, ...}}
    booked_slots_by_doctor = {}
    for appt in all_appointments: 
        slot_key = f"{appt.consultation_type}_{appt.appointment_date.strftime('%Y-%m-%d')}_{appt.appointment_date.strftime('%H:%M')}" 
        booked_slots_by_doctor.setdefault(appt.doctor_id, set()).add(slot_key) 
    # --- End Optimization ---

    for doctor in doctors_list:
        if not isinstance(doctor.available_slots, dict):
            doctor.available_slots = {}
            continue
        
        valid_slots = {}
        booked_slot_times = booked_slots_by_doctor.get(doctor.id, set())

        # Normalize slots into a unified structure: {'online': {...}, 'in-person': {...}}
        normalized_slots = {}
        is_new_structure = 'online' in doctor.available_slots or 'in-person' in doctor.available_slots

        if is_new_structure:
            normalized_slots = doctor.available_slots
        else: # Handle old structure for backward compatibility
            # Default old slots to the doctor's primary consultation type, or 'In-Person'
            default_type = 'in-person' if doctor.consultation_types in ['In-Person', 'Both'] else 'online'
            normalized_slots = {default_type: doctor.available_slots}

        # Process the normalized structure
        for consult_type, date_slots in normalized_slots.items():
            if consult_type not in ['online', 'in-person'] or not isinstance(date_slots, dict):
                continue
            
            valid_type_slots = {}
            for slot_date_str, times in date_slots.items():
                try:
                    slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
                    if slot_date >= today and isinstance(times, list):
                        available_times = []
                        for time_str in times:
                            slot_datetime = datetime.strptime(f"{slot_date_str} {time_str}", '%Y-%m-%d %H:%M')
                            slot_key = f"{consult_type}_{slot_date_str}_{time_str}"
                            if slot_datetime > now and slot_key not in booked_slot_times:
                                available_times.append(time_str)
                        if available_times:
                            valid_type_slots[slot_date_str] = available_times
                except (ValueError, TypeError):
                    continue
            if valid_type_slots:
                valid_slots[consult_type] = valid_type_slots

        doctor.available_slots = valid_slots
    return doctors_list


def _chatbot_action(label, url=None, style="primary", message=None):
    action = {"label": label, "style": style}
    if url:
        action["url"] = url
    if message:
        action["message"] = message
    return action


def _chatbot_logged_in_actions():
    return [
        _chatbot_action("Dashboard", message="show dashboard"),
        _chatbot_action("My appointments", message="show my appointments"),
        _chatbot_action("My profile", style="secondary", message="show my profile"),
    ]


def _chatbot_faq_response(message):
    normalized = re.sub(r"[^a-z0-9\s]", "", message.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    faq = CHATBOT_FAQS.get(normalized)
    if not faq:
        return None

    actions = []
    for label, endpoint, style in faq["actions"]:
        if endpoint in {"login", "register"} and "patient_id" in session:
            if not any(action["label"] == "Dashboard" for action in actions):
                actions.append(_chatbot_action("Dashboard", style=style, message="show dashboard"))
            continue

        if endpoint in {"list_conversations", "my_appointments"} and "patient_id" not in session:
            actions.append(_chatbot_action("Login", style=style, message="how do i login"))
        else:
            actions.append(_chatbot_action(label, style=style, message=label))
    return {"reply": faq["reply"], "actions": actions}


def _format_doctor_summary(doctor):
    consultation = doctor.consultation_types or "Not specified"
    next_slot = None
    next_type = None

    if isinstance(doctor.available_slots, dict):
        for consult_type, date_slots in doctor.available_slots.items():
            if not isinstance(date_slots, dict):
                continue
            for date_str, times in date_slots.items():
                if not isinstance(times, list):
                    continue
                for time_str in times:
                    try:
                        slot_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
                    except ValueError:
                        continue
                    if not next_slot or slot_dt < next_slot:
                        next_slot = slot_dt
                        next_type = consult_type

    slot_text = "No upcoming slots available"
    if next_slot:
        slot_text = f"Next slot: {next_slot.strftime('%b %d %I:%M %p')} ({next_type.title()})"

    return (
        f"Dr. {doctor.doctor_name} — {doctor.specialization} — {doctor.hospital_name}, {doctor.location} — "
        f"★{doctor.rating:.1f} — {consultation} — {slot_text}"
    )


def _chatbot_search_response(message):
    entities = extract_entities_from_query(message)
    symptom = (entities.get("symptom") or message).strip()
    locations = entities.get("locations") or []

    if not locations:
        location_match = re.search(r"\b(?:in|near|at)\s+([a-zA-Z\s]+)$", message, re.IGNORECASE)
        if location_match:
            matched_location = location_match.group(1).strip()
            locations = [] if matched_location.lower() == "me" else [matched_location]
            symptom = message[:location_match.start()].strip()

    symptom = re.sub(r"\b(find|search|show|need|want|a|an|all|list|doctor|doctors|dr|specialist|for|near|me)\b", " ", symptom, flags=re.IGNORECASE)
    symptom = re.sub(r"\s+", " ", symptom).strip()

    normalized_message = _normalize_chatbot_text(message)
    if normalized_message in {"doctor", "doctors", "show doctors", "show doctors list", "doctors list", "list doctors", "all doctors"}:
        symptom = ""

    query = Doctor.query
    specialist = None
    search_term = symptom

    if not search_term:
        # Generic doctor requests like "show doctors" should return top doctors.
        search_term = ""

    if search_term:
        mapping_result = map_disease_to_specialist(search_term)
        specialist = mapping_result.get("specialist")
        if specialist:
            query = query.filter(Doctor.specialization == specialist)
        else:
            fuzzy_term = f"%{search_term}%"
            query = query.filter(db.or_(
                Doctor.doctor_name.ilike(fuzzy_term),
                Doctor.specialization.ilike(fuzzy_term),
                Doctor.location.ilike(fuzzy_term),
            ))

    if locations:
        all_nearby_locations = set()
        for location in locations:
            all_nearby_locations.update(get_nearby_locations(location))
        if all_nearby_locations:
            query = query.filter(Doctor.location.in_(list(all_nearby_locations)))

    doctors = query.order_by(Doctor.rating.desc()).limit(5).all()
    _filter_doctor_slots(doctors)

    if doctors:
        displayed = min(len(doctors), 3)
        doctor_lines = [
            _format_doctor_summary(doctor)
            for doctor in doctors[:displayed]
        ]
        specialty_text = f" for {specialist}" if specialist else ""
        location_text = f" near {', '.join(locations)}" if locations else ""
        response_prefix = (
            f"I found {len(doctors)} doctor option(s){specialty_text}{location_text}. "
            f"Here are the top {displayed}:\n"
        )
        action_buttons = [
            _chatbot_action("Search again", message="find doctor"),
            _chatbot_action("Book appointment help", message="how do i book an appointment"),
        ]

        return {
            "reply": response_prefix + "\n".join(doctor_lines),
            "actions": action_buttons,
        }

    return {
        "reply": "I could not find a strong doctor match for that yet. Try a symptom, specialty, or city, like 'skin doctor in Hyderabad'.",
        "actions": [
            _chatbot_action("Show doctors", message="show doctors list"),
            _chatbot_action("Search again", message="find doctor"),
        ],
    }


def _clean_chatbot_rag_answer(answer, question=""):
    return format_user_rag_response(answer, question=question)


def _chatbot_rag_response(message, actions=None):
    if not message or not message.strip():
        return None

    try:
        rag_result = generate_rag_answer(message, top_k=3)
    except Exception:
        return None

    answer = _clean_chatbot_rag_answer(rag_result.get("answer"), message)
    if not answer:
        return None

    return {"reply": answer, "actions": actions or []}


def _chatbot_activity_response(message):
    normalized = _normalize_chatbot_text(message)

    if any(term in normalized for term in ["login", "sign in"]):
        if "patient_id" in session:
            return {"reply": "You are already logged in.", "actions": _chatbot_logged_in_actions()}
        return {
            "reply": "Login needs username and password. Use the Login menu when you want to sign in.",
            "actions": [],
        }

    if any(term in normalized for term in ["register", "signup", "create account"]):
        if "patient_id" in session:
            return {"reply": "You are already registered and logged in.", "actions": _chatbot_logged_in_actions()}
        return {
            "reply": "Register with name, username, mobile, location, password, then verify your account.",
            "actions": [],
        }

    if any(term in normalized for term in ["dashboard", "analytics", "stats"]):
        if "patient_id" not in session:
            return {"reply": "Login is required to view dashboard details.", "actions": [_chatbot_action("Login help", message="how do i login")]}

        appointment_count = Appointment.query.filter_by(user_id=session["patient_id"]).count()
        unread_count = Message.query.filter_by(
            patient_id=session["patient_id"],
            sender_type="doctor",
            is_read=False,
        ).count()
        return {
            "reply": f"Dashboard: {appointment_count} appointments, {unread_count} unread messages.",
            "actions": [_chatbot_action("Appointments", message="show my appointments"), _chatbot_action("Profile", message="show my profile")],
        }

    if any(term in normalized for term in ["my profile", "profile", "my account"]):
        if "patient_id" not in session:
            return {"reply": "Login is required to view your profile.", "actions": [_chatbot_action("Login help", message="how do i login")]}

        patient = Patient.query.get(session["patient_id"])
        profile_text = f"Profile: {patient.name}, {patient.mobile}, {patient.location}."
        return {"reply": profile_text, "actions": []}

    if any(term in normalized for term in ["my appointments", "show my appointments", "view appointments", "appointment history"]):
        if "patient_id" not in session:
            return {"reply": "Login is required to view your appointments.", "actions": [_chatbot_action("Login help", message="how do i login")]}

        appointments = Appointment.query.filter_by(user_id=session["patient_id"]).order_by(
            Appointment.appointment_date.desc()
        ).limit(3).all()
        if not appointments:
            return {
                "reply": "No appointments found.",
                "actions": [_chatbot_action("Find doctors", message="show doctors list")],
            }
        lines = [
            f"- Dr. {appointment.doctor.doctor_name if appointment.doctor else 'Doctor'}: {appointment.status}"
            for appointment in appointments
        ]
        return {"reply": "Recent appointments:\n" + "\n".join(lines), "actions": []}

    if any(term in normalized for term in ["message", "messages", "conversation", "chat with doctor"]):
        if "patient_id" not in session:
            return {"reply": "Login is required to view doctor messages.", "actions": [_chatbot_action("Login help", message="how do i login")]}
        return {"reply": "Messages are available after booking or during follow-up.", "actions": [_chatbot_action("Appointments", message="show my appointments")]}

    if any(term in normalized for term in ["hospital", "hospitals", "clinic", "clinics"]):
        return {
            "reply": "Please tell me your area/location to find hospitals.",
            "actions": [],
        }

    if any(term in normalized for term in ["emergency", "ambulance", "urgent", "112", "102", "108"]):
        return {
            "reply": "Emergency: call 112. Ambulance: call 108 or 102.",
            "actions": [],
        }

    if any(term in normalized for term in ["contact support", "contact us", "support"]):
        return {
            "reply": "Support: call 8179027681 or email t.naresh5422@gmail.com.",
            "actions": [],
        }

    return None


def _chatbot_clarification_response(message):
    normalized = _normalize_chatbot_text(message)
    words = normalized.split()
    if not normalized:
        return {
            "reply": "Please tell me what you need help with.",
            "actions": [],
        }

    complete_platform_terms = [
        "service", "services", "login", "register", "signup", "dashboard", "profile",
        "emergency", "ambulance", "contact", "support", "helpline",
    ]
    if any(term in normalized for term in complete_platform_terms):
        return None

    search_terms = ["doctor", "doctors", "specialist", "appointment", "book", "near me", "nearby"]
    health_terms = [
        "pain", "fever", "cough", "cold", "vomit", "vomiting", "headache", "skin",
        "heart", "eye", "ear", "tooth", "stomach", "pregnancy", "dog", "cat", "pet", "bird",
    ]

    if any(term in normalized for term in search_terms):
        entities = extract_entities_from_query(message)
        symptom = re.sub(
            r"\b(find|search|show|need|want|a|an|doctor|doctors|dr|specialist|appointment|book|for|near|me|nearby|in|at)\b",
            " ",
            (entities.get("symptom") or message),
            flags=re.IGNORECASE,
        )
        symptom = re.sub(r"\s+", " ", symptom).strip()
        locations = entities.get("locations") or []
        missing = []
        if not symptom:
            missing.append("disease/symptom or specialist")
        if not locations and any(term in normalized for term in ["near me", "nearby", "near", "area", "location"]):
            missing.append("area/location")

        if missing:
            session["chatbot_pending"] = {"intent": "doctor_search", "message": message, "missing": missing}
            if len(missing) == 2:
                question = "Which disease/symptom or specialist, and which area/location?"
            elif "area/location" in missing:
                question = "Which area/location should I search in?"
            else:
                question = "Which disease/symptom or specialist do you need?"
            return {"reply": question, "actions": []}

    vague_health = (
        len(words) <= 2
        and any(term in normalized for term in health_terms)
        and not any(term in normalized for term in ["what", "why", "how", "remedy", "cause", "treatment", "consult"])
    )
    if vague_health:
        session["chatbot_pending"] = {"intent": "health_advice", "message": message}
        return {
            "reply": "Please share the body part/disease, age group, and severity. Do you want remedies or doctor consultation?",
            "actions": [],
        }

    too_short = len(words) <= 2 and not any(term in normalized for term in health_terms)
    if too_short:
        session["chatbot_pending"] = {"intent": "general", "message": message}
        return {
            "reply": "Please clarify what you need: doctor, disease/remedy, services, appointment, or location?",
            "actions": [],
        }

    return None


def _merge_chatbot_pending(message):
    pending = session.pop("chatbot_pending", None)
    if not pending:
        return message

    normalized = _normalize_chatbot_text(message)
    if normalized in {"cancel", "stop", "no", "leave it"}:
        return message

    previous = pending.get("message") or ""
    intent = pending.get("intent")
    missing = pending.get("missing") or []
    if intent == "doctor_search" and not re.search(r"\b(find|search|show|doctor|doctors|specialist|appointment|book)\b", message, re.IGNORECASE):
        health_or_specialty_terms = [
            "pain", "fever", "cough", "cold", "skin", "heart", "cardio", "dent", "eye", "ortho",
            "neuro", "pregnancy", "child", "general", "physician", "dermatologist", "dentist",
            "pediatrician", "gynecologist", "veterinary", "vet",
        ]
        location_only = (
            "disease/symptom or specialist" in missing
            and len(normalized.split()) <= 3
            and not any(term in normalized for term in health_or_specialty_terms)
        )
        if location_only:
            session["chatbot_pending"] = {
                "intent": "doctor_search",
                "message": f"{previous} in {message}".strip(),
                "missing": ["disease/symptom or specialist"],
            }
            return previous
        return f"{previous} {message}".strip()
    if intent in {"health_advice", "general"}:
        return f"{previous} {message}".strip()
    return message


def _chatbot_intent_actions(message):
    normalized = _normalize_chatbot_text(message)

    if any(term in normalized for term in ["book", "appointment", "slot", "online consult", "consult online"]):
        return [
            _chatbot_action("Show doctors", message="show doctors list"),
            _chatbot_action("My appointments", message="show my appointments"),
        ]

    if any(term in normalized for term in ["login", "sign in", "register", "signup", "create account"]):
        if "patient_id" in session:
            return _chatbot_logged_in_actions()
        return [
            _chatbot_action("Patient login", message="how do i login"),
            _chatbot_action("Register", message="how do i register"),
        ]

    if any(term in normalized for term in ["dashboard", "profile", "my account"]):
        if "patient_id" in session:
            return [
                _chatbot_action("Dashboard", message="show dashboard"),
                _chatbot_action("My profile", style="secondary", message="show my profile"),
            ]
        return [_chatbot_action("Login", message="how do i login")]

    if any(term in normalized for term in ["hospital", "clinic"]):
        return [_chatbot_action("Find hospitals", message="show hospitals")]

    if any(term in normalized for term in ["message", "chat with doctor", "conversation"]):
        return [_chatbot_action("Messages", message="show messages")]

    if any(term in normalized for term in ["emergency", "ambulance", "urgent", "112", "102", "108"]):
        return [_chatbot_action("Emergency numbers", style="danger", message="emergency helpline number")]

    if any(term in normalized for term in ["contact", "support"]):
        return [_chatbot_action("Contact us", message="contact support")]

    return []


def _is_rag_assistant_question(message):
    normalized = _normalize_chatbot_text(message)
    assistant_patterns = [
        "how to", "how do i", "how can i", "what is", "what are", "tell me", "explain", "can i",
        "connect", "contact doctor", "chat with doctor", "message doctor", "portal", "feature", "workflow",
        "cause", "causes", "caused by", "remedy", "remedies", "treatment", "treat", "prevention",
        "helpline", "emergency number", "first aid", "consult", "who should i consult",
        "dog", "cat", "pet", "bird", "animal", "veterinary", "vet",
        "service", "services", "book", "appointment", "login", "register", "dashboard", "profile",
        "hospital", "clinic", "contact", "support", "emergency", "ambulance",
    ]
    search_patterns = [
        "find doctor", "find doctors", "search doctor", "search doctors", "show doctor", "show doctors",
        "doctor near", "doctors near", "specialist near", "near me",
    ]
    if any(pattern in normalized for pattern in search_patterns):
        return False
    return any(pattern in normalized for pattern in assistant_patterns)


def _build_chatbot_reply(message):
    cleaned = _merge_chatbot_pending(message.strip())
    lowered = cleaned.lower()

    activity_response = _chatbot_activity_response(cleaned)
    if activity_response:
        return activity_response

    clarification = _chatbot_clarification_response(cleaned)
    if clarification:
        return clarification

    if _is_rag_assistant_question(cleaned):
        rag_response = _chatbot_rag_response(cleaned, _chatbot_intent_actions(cleaned))
        if rag_response:
            return rag_response

    if any(phrase in lowered for phrase in ["find doctor", "find doctors", "search doctor", "search doctors", "show doctor", "show doctors", "doctor near", "doctors near"]):
        return _chatbot_search_response(cleaned)

    if any(word in lowered for word in ["doctor", "specialist", "symptom", "pain", "fever", "skin", "heart", "cardio", "dent", "eye", "ortho", "neuro"]):
        rag_response = _chatbot_rag_response(cleaned, _chatbot_intent_actions(cleaned))
        if rag_response:
            return rag_response
        return _chatbot_search_response(cleaned)

    rag_response = _chatbot_rag_response(cleaned, _chatbot_intent_actions(cleaned))
    if rag_response:
        return rag_response

    return {
        "reply": "Please ask about doctors, appointments, hospitals, services, symptoms, or emergency help.",
        "actions": [
            _chatbot_action("Show doctors", message="show doctors list"),
        ],
    }

def setup_routes(app):
    @app.context_processor
    def inject_user_data():
        context = {'patient': None, 'unread_patient_messages': 0}
        if 'patient_id' in session:
            patient = Patient.query.get(session['patient_id'])
            if patient:
                context['patient'] = patient
                context['unread_patient_messages'] = Message.query.filter_by(
                    patient_id=patient.id,
                    sender_type='doctor',
                    is_read=False
                ).count()
        return context

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            # If a 'next' parameter is in the URL, store it in the session
            # We store that in the session to use after successful login.
            next_page = request.args.get('next')
            if next_page:
                session['next_url'] = next_page
            else:
                # If a user navigates to login directly, clear any old 'next' URL.
                session.pop('next_url', None)
            return render_template("login.html")
        # POST: handle login
        username = request.form.get("username")
        password = request.form.get("password")
        patient = Patient.query.filter_by(username=username).first()

        if patient and patient.check_password(password):
            session["patient_id"] = patient.id
            patient.login_count += 1
            patient.status = "login"
            db.session.commit()
            
            # Redirect to the page the user was trying to access, or to the patient homepage.
            next_url = session.pop("next_url", None)
            if next_url:
                return redirect(next_url)
            return redirect(url_for("patient_home"))
        else:
            flash("Invalid username or password", "danger")
        return render_template("login.html")
    
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"].strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            name = request.form.get("name", "").strip()
            mobile = request.form.get("mobile", "").strip()
            email = request.form.get("email", "").strip() or None
            location = request.form.get("location").strip()
            if not mobile:
                flash("MobileNo is required!", "danger")
                return render_template('signup.html')
            if not username or not password or not name or not location:
                flash("Please fill all required fields", "danger")
                return render_template("signup.html")
            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return render_template("signup.html")
            # Check if user already exists
            existing_patient = Patient.query.filter_by(username=username).first()
            if existing_patient:
                flash("Username already taken. Please choose another one.", "warning")
                return render_template("signup.html")
            # Create new user
            patient = Patient(
                username=username,
                name=name,
                mobile=mobile,
                email=email,
                location=location
            )
            patient.set_password(password)
            db.session.add(patient)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("signup.html")

    @app.route("/register")
    def register():
        return render_template("register.html")


    @app.route("/logout")
    def logout():
        patient_id = session.get("patient_id")
        if patient_id:
            patient = Patient.query.get(patient_id)
            if patient:
                patient.status = "logout"
                db.session.commit()
        session.pop("patient_id", None)
        flash("You have been logged out successfully.", "info")
        return redirect(url_for("index"))

    @app.route("/forgot_password", methods=['GET', 'POST'])
    def user_forgot_password():
        # Placeholder for user password reset logic
        return render_template("user_forgot_password.html")


    @app.route("/")
    def index():
        # Fetch 3 doctors to display on the homepage.
        # Order by rating to show top-rated doctors.
        featured_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        _filter_doctor_slots(featured_doctors) # Ensure slots shown are valid
        return render_template("index.html", featured_doctors=featured_doctors)

    @app.route("/home")
    @login_required
    def patient_home():
        patient = Patient.query.get(session['patient_id'])
        top_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        _filter_doctor_slots(top_doctors)
        return render_template("patient_home.html", patient=patient, top_doctors=top_doctors)
    
    @app.route('/browse_doctors')
    def browse_doctors():
        """
        Displays all doctors, paginated and sorted by availability, review count, and rating.
        This page is now public and does not require login.
        """
        page = request.args.get('page', 1, type=int)
        review_count_subq = db.session.query(
            Review.doctor_id,
            func.count(Review.id).label('review_count')
        ).group_by(Review.doctor_id).subquery()
        has_slots_case = case(
            (and_(Doctor.available_slots != None, Doctor.available_slots != {}), 0),
            else_=1
        )
        all_doctors_query = Doctor.query.outerjoin(
            review_count_subq, Doctor.id == review_count_subq.c.doctor_id
        ).order_by(
            has_slots_case.asc(), 
            func.coalesce(review_count_subq.c.review_count, 0).desc(),
            Doctor.rating.desc()
        )

        # Paginate the results, showing 10 doctors per page.
        pagination = all_doctors_query.paginate(page=page, per_page=10, error_out=False)
        all_doctors_list = pagination.items

        # Filter slots to show only valid, available ones
        _filter_doctor_slots(all_doctors_list)

        # Fetch recent searches for the sidebar (only if a user is logged in)
        recent_searches = []
        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()

        return render_template('doctor_finding.html', doctors=all_doctors_list, recent_searches=recent_searches, 
                               datetime=datetime, disease_query="", location_query="",
                               pagination=pagination, page_title="Browse All Doctors")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        patient_id = session["patient_id"]
        now = datetime.now()
        
        # Fetch counts for stats directly from the database for efficiency.
        # Refined total: Exclude expired pending appointments as they are non-events.
        total_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            db.or_(
                Appointment.status != 'Pending',
                Appointment.appointment_date > now
            )
        ).count()
        
        pending_appointments_count = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Pending',
            Appointment.appointment_date > now
        ).count()
        
        confirmed_appointments_count = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Confirmed',
            Appointment.appointment_date > now
        ).count()
        
        # Count unique doctors for completed consultations
        consultations_completed_count = db.session.query(func.count(func.distinct(Appointment.doctor_id))).filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Completed'
        ).scalar() or 0

        # Fetch reviews given by the patient
        reviews_given = Review.query.filter_by(patient_id=patient_id).order_by(Review.timestamp.desc()).all()

        # --- New: Count unique conversations ---
        # A conversation exists if there's an appointment or a message.
        appointment_doctor_ids = db.session.query(Appointment.doctor_id).filter_by(user_id=patient_id).distinct()
        message_doctor_ids = db.session.query(Message.doctor_id).filter_by(patient_id=patient_id).distinct()
        conversation_doctor_ids = {row[0] for row in appointment_doctor_ids.union(message_doctor_ids).all()}
        total_conversations_count = len(conversation_doctor_ids)

        recent_searches = SearchHistory.query.filter_by(patient_id=patient_id).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status.in_(['Pending', 'Confirmed']),
            Appointment.appointment_date >= now
        ).order_by(Appointment.appointment_date.asc()).all()
        
        return render_template("user_dashboard.html", recent_searches=recent_searches, upcoming_appointments=upcoming_appointments, 
                               total_appointments=total_appointments, pending_appointments_count=pending_appointments_count, 
                               confirmed_appointments_count=confirmed_appointments_count, consultations_completed_count=consultations_completed_count,
                               reviews_given=reviews_given, total_conversations_count=total_conversations_count)

    @app.route("/my_appointments")
    @login_required
    def my_appointments():
        patient_id = session['patient_id']
        patient = Patient.query.get(patient_id)
        status_filter = request.args.get('status')
        view_filter = request.args.get('view')
        now = datetime.now()
        
        appointments_query = Appointment.query.filter_by(user_id=patient_id)

        # --- Refactored Appointment Filtering ---
        # This logic now filters out expired appointments from the 'Pending' and 'Confirmed'
        # views to provide a cleaner and more relevant appointment list.
        if status_filter in ['Pending', 'Confirmed']:
            # For Pending and Confirmed tabs, only show upcoming appointments.
            appointments_query = appointments_query.filter(
                Appointment.status == status_filter,
                Appointment.appointment_date > now
            )
        elif status_filter in ['Completed', 'Canceled']:
            # For Completed and Cancelled tabs, show all historical appointments.
            appointments_query = appointments_query.filter_by(status=status_filter)
        else: # No status filter (the "All" tab)
            pass # The base query fetches all appointments, which is correct for the "All" tab.

        appointments = appointments_query.order_by(Appointment.appointment_date.desc()).all()
        
        # Get a set of doctor IDs the patient has already reviewed
        reviewed_doctor_ids = {review.doctor_id for review in Review.query.filter_by(patient_id=patient_id).all()}

        # --- Start: Logic to get all doctors for conversations ---
        # Find all unique doctors the patient has interacted with
        # Use all appointments to build the conversation list, not just the filtered ones
        all_patient_appointments = Appointment.query.filter_by(user_id=patient_id).all()
        doctor_ids = {app.doctor_id for app in all_patient_appointments}
        messages_with_doctors = Message.query.filter_by(patient_id=patient_id).all()
        doctor_ids.update({msg.doctor_id for msg in messages_with_doctors})

        conversations = []
        if doctor_ids:
            doctors = Doctor.query.filter(Doctor.id.in_(doctor_ids)).all()
            
            # Optimized query to get the last message for each conversation
            subq = db.session.query(
                Message.doctor_id,
                func.max(Message.timestamp).label('max_ts')
            ).filter(
                Message.patient_id == patient_id,
                Message.doctor_id.in_(doctor_ids)
            ).group_by(Message.doctor_id).subquery()

            last_messages_q = db.session.query(Message).join(
                subq,
                db.and_(Message.doctor_id == subq.c.doctor_id, Message.timestamp == subq.c.max_ts)
            )
            last_messages_map = {msg.doctor_id: msg for msg in last_messages_q.all()}
            
            for doc in doctors:
                # Count unread messages from this doctor
                unread_count = Message.query.filter_by(
                    patient_id=patient_id, 
                    doctor_id=doc.id, 
                    is_read=False, 
                    sender_type='doctor'
                ).count()
                can_message = patient.can_message_doctor(doc.id)
                conversations.append({
                    'doctor': doc,
                    'last_message': last_messages_map.get(doc.id),
                    'unread_count': unread_count,
                    'can_message': can_message
                })
            
            # Sort conversations by last message time, descending
            conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
        # --- End: Logic to get all doctors for conversations ---

        return render_template('my_appointments.html', appointments=appointments, reviewed_doctor_ids=reviewed_doctor_ids, conversations=conversations, status_filter=status_filter, view_filter=view_filter, now=now)

    @app.route('/submit_review/<int:doctor_id>', methods=['POST'])
    @login_required
    def submit_review(doctor_id):
        patient_id = session['patient_id']
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        appointment_id = request.form.get('appointment_id')

        if not rating or not comment:
            flash('Rating and comment are required.', 'danger')
            return redirect(request.referrer or url_for('my_appointments'))
        
        if not appointment_id:
            flash('A valid appointment is required to submit a review.', 'danger')
            return redirect(request.referrer or url_for('my_appointments'))

        # Check if a review for this APPOINTMENT already exists
        existing_review = Review.query.filter_by(appointment_id=appointment_id).first()
        if existing_review:
            flash('You have already reviewed this appointment.', 'warning')
            return redirect(url_for('my_appointments'))

        # Security check: ensure the appointment belongs to the logged-in patient, the correct doctor, and is completed.
        appointment = Appointment.query.filter_by(
            id=appointment_id, 
            user_id=patient_id, 
            doctor_id=doctor_id,
            status='Completed'
        ).first()

        if not appointment:
            flash('You can only review a completed appointment that belongs to you.', 'danger')
            return redirect(url_for('my_appointments'))

        review = Review(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id,
            rating=int(rating),
            text=comment
        )
        db.session.add(review)

        # Update doctor's average rating
        doctor = Doctor.query.get(doctor_id)
        if doctor:
            all_reviews = Review.query.filter_by(doctor_id=doctor_id).all()
            new_rating = sum(r.rating for r in all_reviews) / len(all_reviews)
            doctor.rating = round(new_rating, 1)
        
        db.session.commit()
        flash('Thank you for your review!', 'success')
        return redirect(url_for('my_appointments'))

    @app.route("/repeat_search", defaults={"search_id": None})
    @app.route("/repeat_search/<int:search_id>", methods = ["GET","POST"])
    @login_required
    def repeat_search(search_id):
        if "patient_id" not in session:
            flash("Please log in to view your search history.", "warning")
            return redirect(url_for("login"))
        search = SearchHistory.query.get(search_id)
        if not search or search.patient_id != session["patient_id"]:
            flash("Unauthorized or invalid search.", "danger")
            return redirect(url_for('dashboard'))

        disease_query = search.disease
        location_query = search.location

        # The main search bar should show the original query.
        # The location bar is not used on the results page for repeated searches.
        location_query = "" # Clear this to avoid it being appended in the template

        mapping_result = map_disease_to_specialist(disease_query)
        specialist = mapping_result["specialist"]
        results = []

        if specialist:
            all_nearby_locations = set()
            # The saved location can be a comma-separated string of multiple locations
            search_locations = [loc.strip() for loc in search.location.split(',')]
            for loc in search_locations:
                if loc:
                    nearby = get_nearby_locations(loc)
                    all_nearby_locations.update(nearby)

            query = Doctor.query.filter(Doctor.specialization == specialist)
            if all_nearby_locations:
                query = query.filter(Doctor.location.in_(list(all_nearby_locations)))
            
            results = query.order_by(Doctor.rating.desc()).all()

            if not results:
                flash(f"We understood you're looking for a '{specialist}', but we couldn't find any in '{search.location}' or nearby areas. You could try a new search.", "info")
        else:
            flash(f"We couldn't identify a specialty for '{disease_query}'. Please try another search.", "warning")

        # Filter out booked slots and past slots (same logic as find_doctor)
        _filter_doctor_slots(results)

        recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()
        return render_template('doctor_finding.html', doctors=results, recent_searches=recent_searches, datetime=datetime,
                               disease_query=disease_query, location_query=location_query)

    @app.route('/find_doctor', methods=['GET', 'POST'])
    def find_doctor():
        # This route is now public. Login is required for booking, not for searching.
        results = []
        recent_searches = []
        location_query = ""
        disease_query = ""
        final_locations = []
        final_symptom = ""

        # If the find_doctor page is accessed directly via GET without any search parameters,
        # it's likely the user wants to browse all doctors. Redirect them to the correct page.
        if request.method == "GET" and not request.args:
            return redirect(url_for('browse_doctors'))

        if request.method == "POST":
            location_input = request.form.get("location", "").strip()
            disease_input = request.form.get("disease", "").strip()

            # --- AI-powered Query Processing ---
            # 1. Use NER on the disease/symptom field to see if it contains a location.
            # This handles queries like "heart pain in Kurnool" in a single input box.
            entities = extract_entities_from_query(disease_input)
            
            final_symptom = entities['symptom']
            extracted_locations = entities['locations']

            # 2. Decide on the final locations. Combine dedicated input and extracted locations.
            final_locations = []
            if location_input:
                # A user might enter "Hyderabad, Tirupati" in the location box
                final_locations.extend([loc.strip() for loc in location_input.split(',')])
            if extracted_locations:
                final_locations.extend(extracted_locations)
            
            # Remove duplicates and empty strings, preserving order
            final_locations = list(dict.fromkeys(filter(None, final_locations)))
            
            # Set variables for displaying in the search bars on the results page.
            disease_query = disease_input
            location_query = location_input

            # Save search to database for POST requests if user is logged in
            if final_locations and disease_input and 'patient_id' in session:
                search = SearchHistory(patient_id=session["patient_id"],
                                       location=", ".join(final_locations), # Store as comma-separated string
                                       disease=disease_input) # Save original query for history
                db.session.add(search)
                db.session.commit()
        
        elif request.method == "GET" and 'disease' in request.args:
            # This handles clicks on specialty cards, e.g., /find_doctor?disease=Cardiologist
            disease_input = request.args.get('disease', '').strip()
            location_input = request.args.get('location', '').strip()
            entities = extract_entities_from_query(disease_input)
            final_symptom = entities['symptom'] or disease_input
            extracted_locations = entities['locations']
            final_locations = []
            if location_input:
                final_locations.extend([loc.strip() for loc in location_input.split(',')])
            if extracted_locations:
                final_locations.extend(extracted_locations)
            final_locations = list(dict.fromkeys(filter(None, final_locations)))
            disease_query = disease_input
            location_query = location_input
            # The flash message is removed as we now support specialty-only searches.

        # --- Flexible Search Logic ---
        # This logic handles searches by symptom, location, or both.
        query = Doctor.query
        specialist = None
        
        # Only proceed with a search if there's something to search for.
        if not final_symptom and not final_locations:
            if request.method == "POST":
                flash("Please enter a symptom, specialty, or location to search.", "info")
        else:
            # 1. Filter by symptom/specialty if provided
            if final_symptom:
                mapping_result = map_disease_to_specialist(final_symptom)
                specialist = mapping_result["specialist"]
                did_you_mean = mapping_result["did_you_mean"]

                if did_you_mean:
                    flash(f"Showing results for '{did_you_mean}', as no exact match was found for '{disease_query}'.", "info")

                if specialist:
                    query = query.filter(Doctor.specialization == specialist)
                else:
                    # If a symptom was provided but no specialty was found, return no results.
                    flash(f"We couldn't identify a specific medical specialty for '{final_symptom}'. Please try rephrasing your search.", "warning")
                    query = query.filter(False) # Effectively returns no results

            # 2. Filter by location if provided
            if final_locations:
                all_nearby_locations = set()
                for loc in final_locations:
                    nearby = get_nearby_locations(loc.strip())
                    all_nearby_locations.update(nearby)
                
                if all_nearby_locations:
                    query = query.filter(Doctor.location.in_(list(all_nearby_locations)))
            
            # 3. Execute the query and get results
            results = query.order_by(Doctor.rating.desc()).all()
            
            # 4. Provide feedback if no results were found
            if not results and (final_symptom or final_locations):
                feedback_parts = []
                if specialist: feedback_parts.append(f"a '{specialist}'")
                elif final_symptom: feedback_parts.append(f"'{final_symptom}'")
                if final_locations: feedback_parts.append(f"in '{', '.join(final_locations)}' or nearby areas")
                if feedback_parts:
                    flash(f"We couldn't find any doctors for {' and '.join(feedback_parts)}. You could try a new search.", "info")

            _filter_doctor_slots(results)

        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()
        
        return render_template('doctor_finding.html', doctors=results, recent_searches=recent_searches, datetime=datetime,
                               disease_query=disease_query, location_query=location_query)
    
    @app.route('/autocomplete')
    def autocomplete():
        """
        Provides real-time search suggestions for the main search bar.
        """
        query = request.args.get('q', '').strip()
        # Don't return suggestions for very short queries to avoid too much noise.
        if len(query) < 2:
            return jsonify([])
        suggestions = get_autocomplete_suggestions(query)
        return jsonify(suggestions)

    @app.route('/autocomplete/location')
    def autocomplete_location():
        """
        Provides real-time search suggestions for location input fields.
        """
        query = request.args.get('q', '').strip()
        # Allow shorter queries for location aliases like 'hyd'
        if len(query) < 1:
            return jsonify([])
        suggestions = get_location_suggestions(query)
        return jsonify(suggestions)

    @app.route('/chatbot/message', methods=['POST'])
    def chatbot_message():
        payload = request.get_json(silent=True) or {}
        message = (payload.get('message') or '').strip()

        if not message:
            return jsonify({
                "reply": "Please type a question so I can help.",
            }), 400

        try:
            response = _build_chatbot_reply(message)
        except Exception as exc:
            current_app.logger.exception("Chatbot response failed: %s", exc)
            response = {
                "reply": "I had trouble processing that. Try asking again in a simpler way.",
                "actions": [
                    _chatbot_action("Show doctors", message="show doctors list"),
                    _chatbot_action("Services", style="secondary", message="what are the services"),
                ],
            }

        response.setdefault("actions", [])
        return jsonify(response)

    @app.route('/rag/query', methods=['POST'])
    def rag_query():
        payload = request.get_json(silent=True) or {}
        question = (payload.get('question') or '').strip()

        if not question:
            return jsonify({"error": "Question is required."}), 400

        try:
            result = generate_rag_answer(question, top_k=4)
        except Exception as exc:
            current_app.logger.exception("RAG query failed: %s", exc)
            return jsonify({"error": "RAG query failed."}), 500

        response = {
            "question": question,
            "answer": _clean_chatbot_rag_answer(result.get("answer"), question),
        }
        if payload.get("include_matches") is True:
            response["matches"] = result.get("matches", [])
        return jsonify(response)

    @app.route("/about")
    def about():
        return render_template("about.html")
    
    @app.route("/contactus")
    def contactus():
        return render_template("contactus.html")
    
    @app.route("/services")
    def services():
        return render_template("services.html")
    
    @app.route('/emergency_services')
    def emergency_services():
        services = [
            {'name': 'National Emergency Number', 'number': '112', 'icon': 'bi-telephone-fill', 'description': 'For all-in-one emergency assistance.'},
            {'name': 'Police', 'number': '100', 'icon': 'bi-shield-shaded', 'description': 'For police assistance and crime reporting.'},
            {'name': 'Fire Brigade', 'number': '101', 'icon': 'bi-fire', 'description': 'For fire-related emergencies.'},
            {'name': 'Ambulance', 'number': '102', 'icon': 'bi-ambulance', 'description': 'For medical emergencies and ambulance services.'},
            {'name': 'Disaster Management', 'number': '108', 'icon': 'bi-cloud-hail', 'description': 'For natural disasters and major incidents.'},
            {'name': 'Women Helpline', 'number': '1091', 'icon': 'bi-gender-female', 'description': 'For women in distress or facing harassment.'},
            {'name': 'Child Helpline', 'number': '1098', 'icon': 'bi-person-hearts', 'description': 'For children in need of care and protection.'},
            {'name': 'Senior Citizen Helpline', 'number': '14567', 'icon': 'bi-person-wheelchair', 'description': 'For assistance to senior citizens.'},
        ]
        return render_template('emergency_services.html', services=services)

    @app.route('/messages')
    @login_required
    def list_conversations():
        patient_id = session['patient_id']
        
        # Find all doctors the patient has had an appointment with
        appointments = Appointment.query.filter_by(user_id=patient_id).all()
        doctor_ids = {app.doctor_id for app in appointments}
        
        # Also include doctors they have messaged
        messages_with_doctors = Message.query.filter_by(patient_id=patient_id).all()
        doctor_ids.update({msg.doctor_id for msg in messages_with_doctors})

        if not doctor_ids:
            return render_template('conversations.html', conversations=[])

        doctors = Doctor.query.filter(Doctor.id.in_(doctor_ids)).all()
        
        # Optimized query to get the last message for each conversation
        subq = db.session.query(
            Message.doctor_id,
            func.max(Message.timestamp).label('max_ts')
        ).filter(
            Message.patient_id == patient_id,
            Message.doctor_id.in_(doctor_ids)
        ).group_by(Message.doctor_id).subquery()

        last_messages_q = db.session.query(Message).join(
            subq,
            db.and_(Message.doctor_id == subq.c.doctor_id, Message.timestamp == subq.c.max_ts)
        )
        last_messages_map = {msg.doctor_id: msg for msg in last_messages_q.all()}
        
        conversations = []
        for doc in doctors:
            conversations.append({
                'doctor': doc,
                'last_message': last_messages_map.get(doc.id)
            })
        
        # Sort conversations by last message time, descending
        conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)

        return render_template('conversations.html', conversations=conversations)

    @app.route('/messages/<int:doctor_id>', methods=['GET', 'POST'])
    @login_required
    def conversation(doctor_id):
        patient_id = session['patient_id']
        patient = Patient.query.get(patient_id)
        doctor = Doctor.query.get_or_404(doctor_id)
        back_url = request.args.get('back_url') or url_for('my_appointments')

        can_message = patient.can_message_doctor(doctor_id)

        if request.method == 'POST':
            if not can_message:
                flash("Messaging is disabled as the follow-up period for your last appointment has ended. Please book a new appointment to re-enable messaging.", "warning")
                return redirect(url_for('conversation', doctor_id=doctor_id, back_url=back_url))

            content = request.form.get('content')
            if content:
                message = Message(patient_id=patient_id, doctor_id=doctor_id, sender_type='patient', content=content)
                db.session.add(message)
                db.session.commit()
            return redirect(url_for('conversation', doctor_id=doctor_id, back_url=back_url))

        # Mark messages from this doctor as read upon opening the chat
        Message.query.filter_by(
            patient_id=patient_id, 
            doctor_id=doctor_id, 
            sender_type='doctor', 
            is_read=False
        ).update({Message.is_read: True})
        db.session.commit()

        messages = Message.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).order_by(Message.timestamp.asc()).all()
        return render_template('conversation.html', doctor=doctor, messages=messages, back_url=back_url, can_message=can_message)

    # Hospital Services
    @app.route('/hospital_finding')
    def hospital_finder():
        hospitals = []
        location_query = request.args.get("location", "").strip()
        if location_query:
            # Re-use the nearby locations logic
            nearby_locations = get_nearby_locations(location_query)
            hospitals = find_hospitals(nearby_locations)
        return render_template('hospital_finder.html', hospitals=hospitals, location_query=location_query)
    
    @app.route("/user_profile", methods=["GET", "POST"])
    def user_profile():
        if "patient_id" not in session:
            flash("Please login first!", "danger")
            return redirect(url_for("login"))

        patient = Patient.query.get(session["patient_id"])

        if request.method == "POST":
            # Update text fields
            patient.name = request.form.get("name", patient.name)
            patient.location = request.form.get("location", patient.location)
            patient.bio = request.form.get("bio", patient.bio)

            # Only update email/mobile if they are not verified
            if not (hasattr(patient, 'email_verified') and patient.email_verified):
                patient.email = request.form.get("email", patient.email)
            if not (hasattr(patient, 'mobile_verified') and patient.mobile_verified):
                patient.mobile = request.form.get("mobile", patient.mobile)

            # Handle profile image upload
            if "image" in request.files:
                file = request.files["image"]
                if file and file.filename != "":
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(filepath)
                    patient.image = f"uploads/{filename}"  # store relative path

            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for("user_profile"))
        return render_template("user_profile.html", patient=patient)

    @app.route('/send_email_verification')
    @login_required
    def send_email_verification():
        # Check if mail is configured before attempting to send.
        is_mail_configured = all([current_app.config.get('MAIL_SERVER'), current_app.config.get('MAIL_USERNAME'), current_app.config.get('MAIL_PASSWORD')])

        if not is_mail_configured:
            # This case is primarily handled by the template disabling the button,
            # but this server-side check is a good fallback.
            flash("The email service is not configured. Please contact support.", "danger")
            return redirect(url_for('user_profile'))

        if not check_gmail_app_password():
            return redirect(url_for('user_profile'))

        patient = Patient.query.get(session['patient_id'])
        if not patient.email:
            flash('Please add an email address to your profile first.', 'warning')
            return redirect(url_for('user_profile'))

        if hasattr(patient, 'email_verified') and patient.email_verified:
            flash('Your email is already verified.', 'info')
            return redirect(url_for('user_profile'))

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        session['email_verification_otp'] = otp
        session['email_to_verify'] = patient.email

        # Send email with OTP
        msg = MailMessage('Verify Your Email for CareSlotly',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[patient.email])
        msg.body = f'Your CareSlotly email verification OTP is: {otp}'
        try:
            mail.send(msg)
            flash(f'An OTP has been sent to {patient.email}. Please check your inbox.', 'info')
        except smtplib.SMTPAuthenticationError as e:
            error_msg = Markup("Email sending failed due to an authentication error. If using Gmail, please use a 16-character <strong>App Password</strong>. <a href='https://myaccount.google.com/apppasswords' target='_blank' class='alert-link'>Generate one here</a>.")
            flash(error_msg, "danger")
            current_app.logger.error(f"SMTPAuthenticationError: {e}. Check MAIL_USERNAME and MAIL_PASSWORD.")
            if current_app.debug:
                flash(Markup(f"DEV MODE: Email sending failed. You can <a href='{url_for('dev_bypass_patient_email_verification')}' class='alert-link'>click here to bypass verification</a>."), 'info')
            return redirect(url_for('user_profile'))

        return redirect(url_for('verify_email_otp'))

    @app.route('/verify_email_otp', methods=['GET', 'POST'])
    @login_required
    def verify_email_otp():
        if 'email_verification_otp' not in session:
            flash('Verification process has expired. Please try again.', 'warning')
            return redirect(url_for('user_profile'))

        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('email_verification_otp'):
                patient = Patient.query.get(session['patient_id'])
                if patient.email == session.get('email_to_verify'):
                    patient.email_verified = True
                    db.session.commit()
                    flash('Your email has been successfully verified!', 'success')
                    # Clean up session
                    session.pop('email_verification_otp', None)
                    session.pop('email_to_verify', None)
                    return redirect(url_for('user_profile'))
                else:
                    flash('Email address has changed. Please restart verification.', 'danger')
                    return redirect(url_for('user_profile'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        
        return render_template('patient_verify_email.html')

    @app.route('/verify_phone_token', methods=['POST'])
    @login_required
    def verify_phone_token():
        """
        Verifies a Firebase Auth ID token sent from the client after successful
        phone number OTP verification.
        """
        id_token = request.json.get('token')
        if not id_token:
            return jsonify({'success': False, 'error': 'No token provided.'}), 400

        try:
            # Verify the ID token is valid and not revoked.
            decoded_token = auth.verify_id_token(id_token)
            firebase_phone_number = decoded_token.get('phone_number')

            patient = Patient.query.get(session['patient_id'])

            # Ensure the number from the token matches the number in the user's profile.
            # Firebase numbers are in E.164 format (e.g., +919876543210).
            if patient.mobile == firebase_phone_number:
                patient.mobile_verified = True
                db.session.commit()
                flash('Your mobile number has been successfully verified!', 'success')
                return jsonify({'success': True})
            else:
                error_msg = f'Verified number ({firebase_phone_number}) does not match your profile number ({patient.mobile}). Please update your profile and try again.'
                return jsonify({'success': False, 'error': error_msg}), 400

        except auth.InvalidIdTokenError:
            return jsonify({'success': False, 'error': 'The provided token is invalid.'}), 401
        except Exception as e:
            current_app.logger.error(f"Firebase token verification failed for patient {session['patient_id']}: {e}")
            return jsonify({'success': False, 'error': 'An internal server error occurred during verification.'}), 500

    @app.route('/dev/bypass_patient_mobile_verification')
    @login_required
    def dev_bypass_patient_mobile_verification():
        """
        A developer-only route to bypass mobile verification without Firebase.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        patient = Patient.query.get(session['patient_id'])
        patient.mobile_verified = True
        db.session.commit()
        flash('DEV MODE: Mobile number verification bypassed.', 'success')
        return redirect(url_for('user_profile'))

    @app.route('/dev/bypass_patient_email_verification')
    @login_required
    def dev_bypass_patient_email_verification():
        """
        A developer-only route to bypass email verification without sending an email.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        patient = Patient.query.get(session['patient_id'])
        patient.email_verified = True
        db.session.commit()
        flash('DEV MODE: Email verification bypassed.', 'success')
        return redirect(url_for('user_profile'))

    @app.route('/hospital_doctor')
    @login_required
    def hospital_doctor():
        return render_template('hospital_doctor.html')

    @app.route('/hospital_reviews')
    @login_required
    def hospital_reviews():
        return render_template('hospital_reviews.html')

    @app.route('/doctor/<int:doctor_id>', methods=['GET', 'POST'])
    @login_required
    def view_doctor_profile(doctor_id):
        # Fetch doctor details from the database
        doctor = Doctor.query.get_or_404(doctor_id)
        if not doctor:
            return "Doctor not found", 404

        # Use the centralized helper to filter out past and booked slots.
        _filter_doctor_slots([doctor])

        # Ensure doctor has slots before proceeding to the general booking page
        if not doctor.available_slots and not (request.args.get('date') and request.args.get('time')):
            flash(f"Dr. {doctor.doctor_name} has no available slots for booking. Please check back later.", "warning")
            return redirect(request.referrer or url_for('find_doctor'))

        # Pre-fill from query parameters if available
        preselected_date = request.args.get('date')
        preselected_time = request.args.get('time')
        preselected_type = request.args.get('type')

        if request.method == 'POST':
            reason = request.form.get('reason')
            consultation_for = request.form.get('consultation_for', 'Self')
            patient_id = session.get('patient_id')
            consultation_type = request.form.get('consultation_type', 'In-Person')
            payment_option = request.form.get('payment_option')
            appointment_date = None

            # Check if booking is based on pre-defined slots
            if 'appointment_time' in request.form:
                slot_time_str = request.form.get('appointment_time')
                slot_date_str = request.form.get('appointment_date') # The date is now from a select input
                if not slot_date_str or not slot_time_str:
                    flash('Invalid slot selection. Please try again.', 'danger')
                    return redirect(url_for('view_doctor_profile', doctor_id=doctor_id))
                appointment_date = datetime.strptime(f"{slot_date_str} {slot_time_str}", '%Y-%m-%d %H:%M')
            else: # Fallback to datetime-local input
                appointment_date_str = request.form.get('appointment_date')
                if not appointment_date_str:
                    flash('Please select a date and time for the appointment.', 'danger')
                    return redirect(url_for('view_doctor_profile', doctor_id=doctor_id))
                appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%dT%H:%M')

            # Determine payment method and status based on user's choice
            payment_method = 'Cash'
            payment_status = 'Pending'
            if payment_option == 'online_prepay':
                payment_method = 'Online'
                # In a real scenario, you would redirect to a payment gateway here.
                # For now, we'll mark it as 'Pending' and assume payment will be handled.
                payment_status = 'Pending' # This would become 'Completed' after a successful payment webhook.

            new_appointment = Appointment(
                user_id=patient_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                consultation_for=consultation_for,
                consultation_type=consultation_type,
                reason=reason,
                payment_method=payment_method,
                payment_status=payment_status
            )
            db.session.add(new_appointment)
            db.session.commit()

            flash(f'Appointment requested with {doctor.doctor_name}. You will be notified upon confirmation.', 'success')
            
            # --- Refactor: Redirect back to the last search results ---
            last_search = session.get('last_search_query', {})
            if last_search.get('disease') or last_search.get('location'):
                return redirect(url_for('find_doctor', disease=last_search.get('disease', ''), location=last_search.get('location', '')))
            # Fallback to browse_doctors if no search is in session
            return redirect(url_for('browse_doctors'))

        return render_template('book_appointment.html', doctor=doctor, preselected_date=preselected_date, preselected_time=preselected_time, preselected_type=preselected_type)

    @app.route('/send_patient_mobile_verification')
    @login_required
    def send_patient_mobile_verification():
        # Check if Twilio is configured
        required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']
        if not all(current_app.config.get(var) for var in required_vars):
            flash("The SMS service is not configured. Please contact support.", "danger")
            return redirect(url_for('user_profile'))

        patient = Patient.query.get(session['patient_id'])
        if not patient.mobile:
            flash('Please add a mobile number to your profile first.', 'warning')
            return redirect(url_for('user_profile'))

        if getattr(patient, 'mobile_verified', False):
            flash('Your mobile number is already verified.', 'info')
            return redirect(url_for('user_profile'))

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        session['patient_mobile_verification_otp'] = otp
        session['patient_mobile_to_verify'] = patient.mobile

        # Send SMS with OTP via Twilio
        try:
            current_app.logger.info(f"Attempting to send OTP to patient number: {patient.mobile}")
            client = Client(current_app.config['TWILIO_ACCOUNT_SID'], current_app.config['TWILIO_AUTH_TOKEN'])
            message = client.messages.create(
                body=f"Your CareSlotly account mobile verification OTP is: {otp}",
                from_=current_app.config['TWILIO_PHONE_NUMBER'],
                to=patient.mobile
            )
            flash(f'An OTP has been sent to {patient.mobile}.', 'info')
        except exceptions.TwilioRestException as e:
            # Log the specific error from Twilio for debugging
            current_app.logger.error(f"Twilio API error for patient verification: {e.msg} (Code: {e.code})")
            flash("Failed to send OTP. Please check your mobile number or try again later.", "danger")
            if current_app.debug:
                # In debug mode, show the specific Twilio error to the developer
                flash(Markup(f"<b>DEV MODE DEBUG:</b> Twilio Error Code {e.code} - {e.msg}. <a href='https://www.twilio.com/docs/api/errors/{e.code}' target='_blank' class='alert-link'>More info here.</a>"), "warning")
        except Exception as e:
            current_app.logger.error(f"Twilio failed to send SMS for patient verification: {e}")
            flash("Failed to send OTP. Please check your mobile number or try again later.", "danger")
            if current_app.debug:
                flash(Markup(f"DEV MODE: SMS sending failed. You can <a href='{url_for('dev_bypass_patient_mobile_verification')}' class='alert-link'>click here to bypass verification</a>."), 'info')
            return redirect(url_for('user_profile'))

        return redirect(url_for('verify_patient_mobile'))

    @app.route('/verify_patient_mobile', methods=['GET', 'POST'])
    @login_required
    def verify_patient_mobile():
        if 'patient_mobile_verification_otp' not in session:
            flash('Verification process has expired. Please try again.', 'warning')
            return redirect(url_for('user_profile'))

        mobile_number = session.get('patient_mobile_to_verify', '')
        hidden_mobile_number = ''
        # Create a masked version of the number, e.g., '*******3210'
        if len(mobile_number) > 4:
            hidden_mobile_number = '*' * (len(mobile_number) - 4) + mobile_number[-4:]


        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('patient_mobile_verification_otp'):
                patient = Patient.query.get(session['patient_id'])
                if patient.mobile == session.get('patient_mobile_to_verify'):
                    patient.mobile_verified = True
                    db.session.commit()
                    flash('Your mobile number has been successfully verified!', 'success')
                    session.pop('patient_mobile_verification_otp', None)
                    session.pop('patient_mobile_to_verify', None)
                    return redirect(url_for('user_profile'))
                else:
                    flash('Mobile number has changed. Please restart verification.', 'danger')
                    return redirect(url_for('user_profile'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        
        return render_template('patient_verify_mobile.html', hidden_mobile_number=hidden_mobile_number)
