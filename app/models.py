from app.extension import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    doctor_name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(120), nullable=False)
    mobile_no = db.Column(db.String(20), nullable=False)
    email_id = db.Column(db.String(120))
    location = db.Column(db.String(120), nullable=False)
    experience = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    hospital_name = db.Column(db.String(120))
    hospital_address = db.Column(db.String(255))
    hospital_contact = db.Column(db.String(20))
    bio = db.Column(db.Text, nullable=True)
    education = db.Column(db.String(255), nullable=True) # e.g., "MBBS, MD"
    certifications = db.Column(db.Text, nullable=True) # Comma-separated
    available_slots = db.Column(db.JSON, nullable=True) # Store available time slots
    image = db.Column(db.String(200), nullable=True)  # Path to profile image
    reviews = db.relationship('Review', backref='doctor', lazy=True, cascade="all, delete-orphan")
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

    def __repr__(self):
        return f"<Patient {self.username}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
    
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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='reviews')

    def __repr__(self):
        return f"<Review for Doctor {self.doctor_id} by Patient {self.patient_id}>"

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    consultation_for = db.Column(db.String(50), default='Self') # e.g., Self, Spouse, Child
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending') # e.g., Pending, Confirmed, Completed, Canceled
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
