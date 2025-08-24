from services.location_service import get_nearby_locations
from services.disease_service import map_disease_to_specialist
from services.doctor_service import find_doctors

def handle_request(location, disease):
    nearby_locations = get_nearby_locations(location)
    specialist = map_disease_to_specialist(disease)
    doctors = find_doctors(nearby_locations, specialist)
    return doctors
