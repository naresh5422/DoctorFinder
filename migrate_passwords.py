import os
from app.main import create_app
from app.models import Doctor
from app.extension import db
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def migrate_doctor_passwords():
    """
    Finds doctors with plain-text passwords and hashes them.
    This is a one-time migration script.
    """
    app = create_app()
    with app.app_context():
        doctors_to_update = Doctor.query.all()
        updated_count = 0
        for doctor in doctors_to_update:
            # A simple check to see if the password is likely un-hashed.
            # Werkzeug hashes start with 'pbkdf2:sha256:'.
            if not doctor.password.startswith('pbkdf2:sha256:'):
                print(f"Updating password for doctor: {doctor.username}")
                doctor.set_password(doctor.password) # Hash the existing plain-text password
                updated_count += 1
        db.session.commit()
        print(f"Password migration complete. Updated {updated_count} doctor(s).")

if __name__ == '__main__':
    migrate_doctor_passwords()