def map_disease_to_specialist(disease):
    mapping = {
        "diabetes": "Endocrinologist",
        "fever": "General Physician",
        "asthma": "Pulmonologist",
        "skin rash": "Dermatologist",
        "tooth pain": "Dentist"
    }
    return mapping.get(disease.lower(), "General Physician")
