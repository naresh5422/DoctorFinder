from flask import render_template, request, session, redirect, url_for, flash
from app.services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist, find_hospitals, get_featured_hospitals
from app.models import SearchHistory, Patient, Doctor, Appointment, Review, Message
import os
import random
from werkzeug.utils import secure_filename
from app.extension import db, mail, login_required, doctor_login_required
from datetime import datetime, date
from sqlalchemy import func
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_mail import Message as MailMessage # Alias to avoid name conflict with model
from twilio.rest import Client


def _filter_doctor_slots(doctors_list):
    """
    A helper function to filter a list of doctors' available_slots.
    It removes past slots and already booked slots.
    """
    today = date.today()
    now = datetime.now()
    for doctor in doctors_list:
        if not isinstance(doctor.available_slots, dict):
            doctor.available_slots = {}
            continue
        
        valid_slots = {}
        # Get all appointments for this doctor on their available dates
        appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date.cast(db.Date).in_(doctor.available_slots.keys()),
            Appointment.status.in_(['Pending', 'Confirmed'])
        ).all()
        booked_slot_times = {f"{appt.appointment_date.strftime('%Y-%m-%d')}_{appt.appointment_date.strftime('%H:%M')}" for appt in appointments}

        for slot_date_str, times in doctor.available_slots.items():
            try:
                slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
                if slot_date >= today:
                    available_times = []
                    for time_str in times:
                        slot_datetime = datetime.strptime(f"{slot_date_str} {time_str}", '%Y-%m-%d %H:%M')
                        if slot_datetime > now and f"{slot_date_str}_{time_str}" not in booked_slot_times:
                            available_times.append(time_str)
                    if available_times:
                        valid_slots[slot_date_str] = available_times
            except (ValueError, TypeError):
                continue
        doctor.available_slots = valid_slots
    return doctors_list

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
        # In the future, you could order this by rating: .order_by(Doctor.rating.desc())
        featured_doctors = Doctor.query.limit(3).all()
        featured_hospitals = get_featured_hospitals(limit=3)
        return render_template("index.html", featured_doctors=featured_doctors, featured_hospitals=featured_hospitals)

    @app.route("/home")
    @login_required
    def patient_home():
        patient = Patient.query.get(session['patient_id'])
        # Fetch top-rated doctors to display on the patient's homepage
        top_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        _filter_doctor_slots(top_doctors)
        return render_template("patient_home.html", patient=patient, top_doctors=top_doctors)
    
    @app.route('/browse_doctors')
    @login_required
    def browse_doctors():
        """Displays all doctors, sorted by rating."""
        # Fetch all doctors, sorted by rating (high priority)
        all_doctors_list = Doctor.query.order_by(Doctor.rating.desc()).all()

        # Filter slots to show only valid, available ones
        _filter_doctor_slots(all_doctors_list)

        # Fetch recent searches for the sidebar
        recent_searches = []
        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()

        return render_template('doctor_finding.html', doctors=all_doctors_list, recent_searches=recent_searches, 
                               datetime=datetime, disease_query="",
                               location_query="")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        patient_id = session["patient_id"]
        
        # Fetch all appointments for stats
        all_appointments = Appointment.query.filter_by(user_id=patient_id).all()
        total_appointments = len(all_appointments) 
        pending_appointments_count = sum(1 for a in all_appointments if a.status == 'Pending')
        confirmed_appointments_count = sum(1 for a in all_appointments if a.status == 'Confirmed')
        
        # Count unique doctors for completed consultations
        consultations_completed_count = len({a.doctor_id for a in all_appointments if a.status == 'Completed'})

        # Fetch reviews given by the patient
        reviews_given = Review.query.filter_by(patient_id=patient_id).order_by(Review.timestamp.desc()).all()

        # --- New: Count unique conversations ---
        # A conversation exists if there's an appointment or a message.
        conversation_doctor_ids = {app.doctor_id for app in all_appointments}
        messages_with_doctors = Message.query.filter_by(patient_id=patient_id).all()
        conversation_doctor_ids.update({msg.doctor_id for msg in messages_with_doctors})
        total_conversations_count = len(conversation_doctor_ids)

        recent_searches = SearchHistory.query.filter_by(patient_id=patient_id).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status.in_(['Pending', 'Confirmed']),
            Appointment.appointment_date >= datetime.now()
        ).order_by(Appointment.appointment_date.asc()).all()
        
        return render_template("user_dashboard.html", recent_searches=recent_searches, upcoming_appointments=upcoming_appointments, 
                               total_appointments=total_appointments, pending_appointments_count=pending_appointments_count, 
                               confirmed_appointments_count=confirmed_appointments_count, consultations_completed_count=consultations_completed_count,
                               reviews_given=reviews_given, total_conversations_count=total_conversations_count)

    @app.route("/my_appointments")
    @login_required
    def my_appointments():
        patient_id = session['patient_id']
        status_filter = request.args.get('status')
        view_filter = request.args.get('view')
        
        # Fetch all appointments for the patient
        appointments_query = Appointment.query.filter_by(user_id=patient_id)
        if status_filter and status_filter in ['Pending', 'Confirmed', 'Completed', 'Cancelled']:
            appointments_query = appointments_query.filter_by(status=status_filter)

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
                conversations.append({
                    'doctor': doc,
                    'last_message': last_messages_map.get(doc.id),
                    'unread_count': unread_count
                })
            
            # Sort conversations by last message time, descending
            conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
        # --- End: Logic to get all doctors for conversations ---

        return render_template('my_appointments.html', appointments=appointments, reviewed_doctor_ids=reviewed_doctor_ids, conversations=conversations, status_filter=status_filter, view_filter=view_filter)

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

        # Check if a review for this doctor by this patient already exists
        existing_review = Review.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).first()
        if existing_review:
            flash('You have already reviewed this doctor.', 'warning')
            return redirect(url_for('my_appointments'))

        review = Review(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id,
            rating=int(rating),
            comment=comment
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

        location_query = search.location
        disease_query = search.disease

        specialist_mapping = map_disease_to_specialist(disease_query)
        specialist = specialist_mapping.split(" - ")[1]
        nearby_locations = get_nearby_locations(location_query.strip().lower())
        results = Doctor.query.filter(
            Doctor.location.in_(nearby_locations),
            Doctor.specialization == specialist
        ).all()

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

        if request.method == "POST":
            location_query = request.form.get("location", "")
            disease_query = request.form.get("disease")
            # 🔹 Map layman term OR specialist to professional mapping
            # Save search to database for POST requests if user is logged in
            if location_query and disease_query and 'patient_id' in session:
                search = SearchHistory(patient_id=session["patient_id"],
                                       location=location_query,
                                       disease=disease_query)
                db.session.add(search)
                db.session.commit()
        
        elif request.method == "GET" and 'disease' in request.args:
            disease_query = request.args.get('disease')
            # For GET, we can default to the user's location if they are logged in
            if 'patient_id' in session:
                patient = Patient.query.get(session['patient_id'])
                location_query = patient.location if patient else ""
                if not location_query:
                    flash("To browse by specialty, please set a location in your profile or use the search bar.", "info")

        if disease_query and location_query:
            specialist_mapping = map_disease_to_specialist(disease_query)
            specialist = specialist_mapping.split(" - ")[1]
            ## Doctor search logic
            nearby_locations = get_nearby_locations(location_query.strip().lower())
            results = Doctor.query.filter(
                Doctor.location.in_(nearby_locations),
                Doctor.specialization == specialist
            ).all()

            # Filter out booked slots and past slots
            _filter_doctor_slots(results)

        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()
        
        return render_template('doctor_finding.html', doctors=results, recent_searches=recent_searches, datetime=datetime,
                               disease_query=disease_query, location_query=location_query)
    
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
        doctor = Doctor.query.get_or_404(doctor_id)
        back_url = request.args.get('back_url') or url_for('my_appointments')

        if request.method == 'POST':
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
        return render_template('conversation.html', doctor=doctor, messages=messages, back_url=back_url)

    # Doctor-side Messaging
    @app.route('/doctor/messages')
    @doctor_login_required
    def doctor_list_conversations():
        doctor_id = session['doctor_id']
        
        # Subquery to get the last message for each patient conversation
        subq = db.session.query(
            Message.patient_id,
            func.max(Message.timestamp).label('max_ts')
        ).filter(Message.doctor_id == doctor_id).group_by(Message.patient_id).subquery()

        # Join to get the full last message details
        last_messages_q = db.session.query(Message).join(
            subq,
            db.and_(Message.patient_id == subq.c.patient_id, Message.timestamp == subq.c.max_ts)
        )
        
        conversations = []
        for msg in last_messages_q.all():
            patient = Patient.query.get(msg.patient_id)
            # Count unread messages from this patient
            unread_count = Message.query.filter_by(
                doctor_id=doctor_id, 
                patient_id=patient.id, 
                is_read=False, 
                sender_type='patient'
            ).count()
            conversations.append({
                'patient': patient,
                'last_message': msg,
                'unread_count': unread_count
            })
        
        # Sort conversations by the timestamp of the last message
        conversations.sort(key=lambda x: x['last_message'].timestamp, reverse=True)

        return render_template('doctor_conversations.html', conversations=conversations)

    @app.route('/doctor/messages/<int:patient_id>', methods=['GET', 'POST'])
    @doctor_login_required
    def doctor_conversation(patient_id):
        doctor_id = session['doctor_id']
        patient = Patient.query.get_or_404(patient_id)

        if request.method == 'POST':
            content = request.form.get('content')
            if content:
                message = Message(patient_id=patient_id, doctor_id=doctor_id, sender_type='doctor', content=content)
                db.session.add(message)
                db.session.commit()
            return redirect(url_for('doctor_conversation', patient_id=patient_id))

        # Mark messages from this patient as read upon opening the chat
        Message.query.filter_by(
            doctor_id=doctor_id, 
            patient_id=patient_id, 
            sender_type='patient', 
            is_read=False
        ).update({Message.is_read: True})
        db.session.commit()

        messages = Message.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).order_by(Message.timestamp.asc()).all()
        return render_template('doctor_conversation.html', patient=patient, messages=messages)

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
        patient = Patient.query.get(session['patient_id'])
        if not patient.email:
            flash('Please add an email address to your profile first.', 'warning')
            return redirect(url_for('user_profile'))

        # Check if the attribute exists and if it's true
        if hasattr(patient, 'email_verified') and patient.email_verified:
            flash('Your email is already verified.', 'info')
            return redirect(url_for('user_profile'))

        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        token = s.dumps(patient.email, salt='email-verification-salt')
        
        verify_url = url_for('verify_email', token=token, _external=True)
        msg = MailMessage('Verify Your Email for CareConnect',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[patient.email])
        msg.body = f'''Please click the following link to verify your email address:
{verify_url}
If you did not request this, please ignore this email.
'''
        mail.send(msg)
        flash(f'A verification link has been sent to {patient.email}. Please check your inbox.', 'info')
        return redirect(url_for('user_profile'))

    @app.route('/verify_email/<token>')
    @login_required
    def verify_email(token):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='email-verification-salt', max_age=3600) # 1 hour expiry
        except (SignatureExpired, BadTimeSignature):
            flash('The verification link is invalid or has expired.', 'danger')
            return redirect(url_for('user_profile'))

        patient = Patient.query.get(session['patient_id'])
        if patient.email == email:
            # Check if the attribute exists before trying to set it
            if hasattr(patient, 'email_verified'):
                patient.email_verified = True
                db.session.commit()
                flash('Your email has been successfully verified!', 'success')
            else:
                # This is a fallback if the DB schema is not updated.
                flash('Email verification feature is not fully configured. Please contact support.', 'warning')
        else:
            flash('There was an error verifying your email. Please try again.', 'danger')
        
        return redirect(url_for('user_profile'))

    @app.route('/send_mobile_verification')
    @login_required
    def send_mobile_verification():
        patient = Patient.query.get(session['patient_id'])
        if not patient.mobile:
            flash('Please add a mobile number to your profile first.', 'warning')
            return redirect(url_for('user_profile'))

        # Check if the attribute exists and if it's true
        if hasattr(patient, 'mobile_verified') and patient.mobile_verified:
            flash('Your mobile number is already verified.', 'info')
            return redirect(url_for('user_profile'))

        otp = str(random.randint(100000, 999999))
        session['mobile_verification_otp'] = otp
        session['mobile_to_verify'] = patient.mobile

        try:
            client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])
            message = client.messages.create(
                body=f"Your CareConnect verification OTP is: {otp}",
                from_=app.config['TWILIO_PHONE_NUMBER'],
                to=patient.mobile # Assuming mobile number is in E.164 format
            )
            flash(f"An OTP has been sent to your mobile number.", "info")
            return redirect(url_for('verify_mobile'))
        except Exception as e:
            flash("Failed to send OTP. Please check your mobile number or try again later.", "danger")
            app.logger.error(f"Twilio failed to send SMS for patient verification: {e}")
            return redirect(url_for('user_profile'))

    @app.route('/verify_mobile', methods=['GET', 'POST'])
    @login_required
    def verify_mobile():
        if 'mobile_verification_otp' not in session:
            flash('Verification process has expired. Please try again.', 'warning')
            return redirect(url_for('user_profile'))

        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('mobile_verification_otp'):
                patient = Patient.query.get(session['patient_id'])
                if patient.mobile == session.get('mobile_to_verify'):
                    # Check if the attribute exists before trying to set it
                    if hasattr(patient, 'mobile_verified'):
                        patient.mobile_verified = True
                        db.session.commit()
                        flash('Your mobile number has been successfully verified!', 'success')
                        # Clean up session
                        session.pop('mobile_verification_otp', None)
                        session.pop('mobile_to_verify', None)
                        return redirect(url_for('user_profile'))
                    else:
                        # This is a fallback if the DB schema is not updated.
                        flash('Mobile verification feature is not fully configured. Please contact support.', 'warning')
                        return redirect(url_for('user_profile'))
                else:
                    flash('Mobile number has changed. Please restart verification.', 'danger')
                    return redirect(url_for('user_profile'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        
        return render_template('patient_verify_mobile.html')

    @app.route('/hospital_doctor')
    @login_required
    def hospital_doctor():
        return render_template('hospital_doctor.html')

    @app.route('/hospital_reviews')
    @login_required
    def hospital_reviews():
        return render_template('hospital_reviews.html')

    @app.route('/book_appointment/<int:doctor_id>', methods=['GET', 'POST'])
    @login_required
    def book_appointment(doctor_id):
        # Fetch doctor details from the database
        doctor = Doctor.query.get_or_404(doctor_id)
        if not doctor:
            return "Doctor not found", 404

        # --- START: Filter out booked and past slots ---
        today = date.today()
        now = datetime.now()

        # Ensure available_slots is a dictionary before processing.
        if not isinstance(doctor.available_slots, dict):
            doctor.available_slots = {}

        if doctor.available_slots:
            valid_slots = {}
            # Get all appointments for this doctor on their available dates
            appointments = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date.cast(db.Date).in_(doctor.available_slots.keys()),
                Appointment.status.in_(['Pending', 'Confirmed'])
            ).all()
            booked_slot_times = {f"{appt.appointment_date.strftime('%Y-%m-%d')}_{appt.appointment_date.strftime('%H:%M')}" for appt in appointments}

            for slot_date_str, times in doctor.available_slots.items():
                try:
                    slot_date = datetime.strptime(slot_date_str, '%Y-%m-%d').date()
                    if slot_date >= today:
                        available_times = []
                        for time_str in times:
                            slot_datetime = datetime.strptime(f"{slot_date_str} {time_str}", '%Y-%m-%d %H:%M')
                            if slot_datetime > now and f"{slot_date_str}_{time_str}" not in booked_slot_times:
                                available_times.append(time_str)
                        if available_times:
                            valid_slots[slot_date_str] = available_times
                except ValueError:
                    continue # Safely skip keys that are not dates
            doctor.available_slots = valid_slots
        # --- END: Slot filtering ---

        # Ensure doctor has slots before proceeding to the general booking page
        if not doctor.available_slots and not (request.args.get('date') and request.args.get('time')):
            flash(f"Dr. {doctor.doctor_name} has no available slots for booking. Please check back later.", "warning")
            return redirect(request.referrer or url_for('find_doctor'))

        # Pre-fill from query parameters if available
        preselected_date = request.args.get('date')
        preselected_time = request.args.get('time')

        if request.method == 'POST':
            reason = request.form.get('reason')
            consultation_for = request.form.get('consultation_for', 'Self')
            patient_id = session.get('patient_id')
            appointment_date = None

            # Check if booking is based on pre-defined slots
            if 'appointment_time' in request.form:
                slot_time_str = request.form.get('appointment_time')
                slot_date_str = request.form.get('appointment_date') # The date is now from a select input
                if not slot_date_str or not slot_time_str:
                    flash('Invalid slot selection. Please try again.', 'danger')
                    return redirect(url_for('book_appointment', doctor_id=doctor_id))
                appointment_date = datetime.strptime(f"{slot_date_str} {slot_time_str}", '%Y-%m-%d %H:%M')
            else: # Fallback to datetime-local input
                appointment_date_str = request.form.get('appointment_date')
                if not appointment_date_str:
                    flash('Please select a date and time for the appointment.', 'danger')
                    return redirect(url_for('book_appointment', doctor_id=doctor_id))
                appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%dT%H:%M')

            new_appointment = Appointment(
                user_id=patient_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                consultation_for=consultation_for,
                reason=reason
            )
            db.session.add(new_appointment)
            db.session.commit()
            flash(f'Appointment requested with {doctor.doctor_name}. You will be notified upon confirmation.', 'success')
            return redirect(url_for('find_doctor'))

        return render_template('book_appointment.html', doctor=doctor, preselected_date=preselected_date, preselected_time=preselected_time)