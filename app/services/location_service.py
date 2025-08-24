def get_nearby_locations(location):
    # Simulated nearby locations
    nearby = {
        "Gajuwaka": ["Gajuwaka", "Visakhapatnam", "NAD Junction"],
        "Hyderabad": ["Hyderabad", "Secunderabad", "Gachibowli"]
    }
    return nearby.get(location, [location])
