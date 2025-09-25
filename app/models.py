from app.extension import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    NMR_ID = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    doctor_name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    mobile_no = db.Column(db.String(20), nullable=False)
    email_id = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    experience = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    hospital_name = db.Column(db.String(120), nullable=False)
    consultation_types = db.Column(db.String(50), nullable=False, default='In-Person') # e.g., 'In-Person', 'Online', 'Both'
    hospital_address = db.Column(db.String(255), nullable=False)
    hospital_contact = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    education = db.Column(db.String(255), nullable=True) # e.g., "MBBS, MD"
    certifications = db.Column(db.Text, nullable=True) # Comma-separated
    available_slots = db.Column(db.JSON, nullable=True) # Store available time slots
    image = db.Column(db.String(200), nullable=True)  # Path to profile image
    reviews = db.relationship('Review', backref='doctor', lazy=True, cascade="all, delete-orphan")
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    mobile_verified = db.Column(db.Boolean, default=False, nullable=False)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

    def __repr__(self):
        return f"<Doctor {self.doctor_name}>"

    @property
    def review_texts(self):
        return [review.text for review in self.reviews]

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))  # Optional
    location = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    login_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(10), default="logout")
    image = db.Column(db.String(200), nullable=True)  # Path to profile image
    bio = db.Column(db.Text, nullable=True)  # Extra details
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    mobile_verified = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Patient {self.username}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def can_message_doctor(self, doctor_id):
        """
        Checks if a patient is allowed to message a doctor.
        Messaging is enabled if there is an upcoming appointment or if the last
        completed appointment is within a 7-day follow-up period.
        """
        from datetime import datetime, timedelta
        MESSAGING_FOLLOW_UP_DAYS = 7
        follow_up_period = timedelta(days=MESSAGING_FOLLOW_UP_DAYS)
        now = datetime.now()

        # 1. Check for any upcoming (Pending or Confirmed) appointments
        upcoming_appointment = Appointment.query.filter(
            Appointment.user_id == self.id,
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(['Pending', 'Confirmed']),
            Appointment.appointment_date > now
        ).first()
        if upcoming_appointment:
            return True

        # 2. Check for a recently completed appointment
        last_completed_appointment = Appointment.query.filter(
            Appointment.user_id == self.id,
            Appointment.doctor_id == doctor_id,
            Appointment.status == 'Completed'
        ).order_by(Appointment.appointment_date.desc()).first()

        if last_completed_appointment:
            if now <= last_completed_appointment.appointment_date + follow_up_period:
                return True

        return False
    
class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    disease = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default = datetime.utcnow)

    def __repr__(self):
        return f"<SearchHistory for Patient {self.patient_id}>"

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False, default=5) # Rating from 1 to 5
    text = db.Column(db.Text, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='reviews')
    appointment = db.relationship('Appointment', backref=db.backref('review', uselist=False))

    def __repr__(self):
        return f"<Review for Doctor {self.doctor_id} by Patient {self.patient_id}>"

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    consultation_for = db.Column(db.String(50), default='Self') # e.g., Self, Spouse, Child
    consultation_type = db.Column(db.String(20), nullable=False, default='In-Person') # 'In-Person' or 'Online'
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending') # e.g., Pending, Confirmed, Completed, Canceled
    payment_method = db.Column(db.String(50), nullable=True) # e.g., 'Online', 'Cash'
    payment_status = db.Column(db.String(50), default='Pending', nullable=False) # e.g., 'Pending', 'Completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='appointments')

    def __repr__(self):
        return f"<Appointment {self.id} with Dr. {self.doctor_id} for Patient {self.user_id}>"

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # 'patient' or 'doctor'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    patient = db.relationship('Patient', backref=db.backref('messages', lazy='dynamic'))
    doctor = db.relationship('Doctor', backref=db.backref('messages', lazy='dynamic'))

    def __repr__(self):
        return f'<Message {self.id}>'

class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False, unique=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medication_details = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    appointment = db.relationship('Appointment', backref=db.backref('prescription', uselist=False, cascade="all, delete-orphan"))
    doctor = db.relationship('Doctor', backref='prescriptions')
    patient = db.relationship('Patient', backref='prescriptions')

    def __repr__(self):
        return f'<Prescription for Appointment {self.appointment_id}>'


# --- Models for Scalable Business Logic ---

class Specialty(db.Model):
    __tablename__ = 'specialties'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Specialty {self.name}>'

class Symptom(db.Model):
    __tablename__ = 'symptoms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'), nullable=False)
    specialty = db.relationship('Specialty', backref=db.backref('symptoms', lazy=True))

    def __repr__(self):
        return f'<Symptom {self.name}>'

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    sub_locations = db.relationship('Location', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    def __repr__(self):
        return f'<Location {self.name}>'

class LocationAlias(db.Model):
    __tablename__ = 'location_aliases'
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(120), unique=True, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    location = db.relationship('Location', backref=db.backref('aliases', lazy=True))
