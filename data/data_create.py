import json
import random

# Sample data pools
doctor_first_names = ["Suresh", "Meena", "Anil", "Priya", "Vikram", "Neha", "Arjun", "Lakshmi", "Ravi", "Kiran",
                      "Divya", "Manoj", "Swathi", "Harish", "Sindhu", "Deepak", "Rajesh", "Pooja", "Ganesh", "Kavya"]
doctor_last_names = ["Reddy", "Kumar", "Sharma", "Gupta", "Varma", "Naidu", "Patel", "Iyer", "Chowdary", "Menon"]

specializations = ["Endocrinologist", "General Physician", "Pulmonologist", "Dermatologist", "Dentist",
                   "Cardiologist", "Neurologist", "Orthopedic", "Pediatrician", "Psychiatrist",
                   "Gynecologist", "ENT Specialist", "Oncologist", "Nephrologist", "Ophthalmologist"]

locations = ["Tirupati", "Renigunta", "Chittoor", "Nellore", "Hyderabad", "Vijayawada", "Guntur",
             "Kurnool", "Anantapur", "Rajahmundry"]

hospitals = [
    {"name": "Apollo Clinic", "address": "AIR Bypass Road, Tirupati", "contact": "0877-2233445"},
    {"name": "Renigunta Medical Center", "address": "Main Road, Renigunta", "contact": "0877-1122334"},
    {"name": "CMC Hospital", "address": "City Center, Chittoor", "contact": "08572-224466"},
    {"name": "Nellore Care Hospital", "address": "Trunk Road, Nellore", "contact": "0861-332211"},
    {"name": "Yashoda Hospital", "address": "Somajiguda, Hyderabad", "contact": "040-12345678"},
    {"name": "Ramesh Hospitals", "address": "MG Road, Vijayawada", "contact": "0866-998877"},
    {"name": "KIMS Hospital", "address": "Guntur Road, Guntur", "contact": "0863-445566"},
    {"name": "Government Hospital", "address": "Main Road, Anantapur", "contact": "08554-778899"},
    {"name": "Sunshine Hospital", "address": "KPHB, Hyderabad", "contact": "040-87654321"},
    {"name": "LV Prasad Eye Institute", "address": "Banjara Hills, Hyderabad", "contact": "040-66554433"},
]

positive_reviews = [
    "Very knowledgeable and caring.",
    "Takes time to explain everything.",
    "Highly recommended for treatment.",
    "Friendly and professional.",
    "Great experience, felt comfortable.",
    "Accurate diagnosis and treatment.",
    "Excellent service and staff.",
    "Really listens to patient concerns."
]

negative_reviews = [
    "Long waiting time.",
    "Felt rushed during consultation.",
    "Staff was not very helpful.",
    "Charges are a bit high.",
    "Appointment process needs improvement.",
    "Consultation was too short.",
    "Did not get enough explanation.",
    "Waiting area could be better."
]

# Generate 100 doctors
doctors = []
for i in range(100):
    id = i+1
    username = f"doctor{id}"
    password = "password"  # In real scenarios, use hashed passwords
    doctor_name = f"Dr. {random.choice(doctor_first_names)} {random.choice(doctor_last_names)}"
    specialization = random.choice(specializations)
    location = random.choice(locations)
    experience = random.randint(3, 35)  # years of experience
    rating = round(random.uniform(3.0, 5.0), 1)  # rating between 3.0 and 5.0
    reviews = random.sample(positive_reviews, 2) + random.sample(negative_reviews, 1)
    hospital = random.choice(hospitals)

    doctor = {
        "id": id,
        "username": username,
        "password": password,
        "doctor_name": doctor_name,
        "specialization": specialization,
        "MobileNo": f"9{random.randint(100000000,999999999)}",
        "EmailId": f"{username}@gmail.com",
        "location": location,
        "experience": experience,
        "rating": rating,
        "reviews": reviews,
        "hospital": hospital
    }

    doctors.append(doctor)

# Save to doctors.json
with open("D:/All_Projects/DoctorFinder/app/data/doctors.json", "w", encoding="utf-8") as f:
    json.dump(doctors, f, indent=4, ensure_ascii=False)

print("✅ doctors.json with 100 records generated successfully!")
