def validate_location(location):
    return isinstance(location, str) and len(location) > 0

def validate_disease(disease):
    return isinstance(disease, str) and len(disease) > 0
