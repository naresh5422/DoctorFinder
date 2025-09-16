from flask import render_template, request, session, redirect, url_for, flash
from app.services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist
from app.models import SearchHistory, Patient, Doctor, Appointment, Review
from werkzeug.utils import secure_filename
from app.extension import db, login_required
from datetime import datetime


def setup_routes(app):
    @app.context_processor
    def inject_user():
        patient = None
        if 'patient_id' in session:
            patient = Patient.query.get(session['patient_id'])
        return dict(patient=patient)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            session["next_url"] = request.args.get("next") or request.referrer
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
            return redirect(url_for("patient_home"))  # Redirect to patient homepage
        else:
            flash("Invalid username or password", "danger")
        return render_template("login.html")
    
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"].strip()
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
        # In the future, you can fetch top-rated doctors to display on the homepage
        # For example: featured_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        # return render_template("index.html", featured_doctors=featured_doctors)
        return render_template("index.html") # Currently no data is passed
    
    @app.route("/home")
    @login_required
    def patient_home():
        patient = Patient.query.get(session['patient_id'])
        return render_template("patient_home.html", patient=patient)
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        patient_id = session["patient_id"]
        
        # Fetch all appointments for stats
        all_appointments = Appointment.query.filter_by(user_id=patient_id).all()
        total_appointments = len(all_appointments)
        pending_appointments_count = len([a for a in all_appointments if a.status == 'Pending'])
        
        # Count unique doctors consulted
        consulted_doctor_ids = {a.doctor_id for a in all_appointments if a.status in ['Confirmed', 'Completed']}
        doctors_consulted_count = len(consulted_doctor_ids)

        # Fetch reviews given by the patient
        reviews_given = Review.query.filter_by(patient_id=patient_id).order_by(Review.timestamp.desc()).all()

        recent_searches = SearchHistory.query.filter_by(patient_id=patient_id).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.appointment_date >= datetime.utcnow()
        ).order_by(Appointment.appointment_date.asc()).all()
        return render_template("user_dashboard.html", recent_searches=recent_searches, upcoming_appointments=upcoming_appointments, total_appointments=total_appointments, pending_appointments_count=pending_appointments_count, doctors_consulted_count=doctors_consulted_count, reviews_given=reviews_given)

    @app.route("/repeat_search", defaults={"search_id": None})
    @app.route("/repeat_search/<int:search_id>", methods = ["GET","POST"])
    @login_required
    def repeat_search(search_id):
        if "patient_id" not in session:
            return redirect(url_for("login"))
        search = SearchHistory.query.get(search_id)
        if not search or search.patient_id != session["patient_id"]:
            return "Unauthorized or invalid search"
        nearby_locations = get_nearby_locations(search.location)
        specialist = map_disease_to_specialist(search.disease)
        results = find_doctors(nearby_locations, specialist)
        recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        return render_template("index.html", results=results, recent_searches=recent_searches)

    @app.route('/find_doctor', methods=['GET', 'POST'])
    @login_required
    def find_doctor():
        results = []
        recent_searchs = []
        if request.method == "POST":
            location = request.form.get("location", "")
            disease = request.form.get("disease")
            # 🔹 Map layman term OR specialist to professional mapping
            specialist_mapping = map_disease_to_specialist(disease)
            specialist = specialist_mapping.split(" - ")[1]
            # Save search to database
            search = SearchHistory(patient_id=session["patient_id"],
                                   location=location,
                                   disease=disease)
            db.session.add(search)
            db.session.commit()
            ## Doctor search logic
            nearby_locations = get_nearby_locations(location.strip().lower())
            results = Doctor.query.filter(
                Doctor.location.in_(nearby_locations),
                Doctor.specialization == specialist
            ).all()

            # Filter out booked slots
            for doctor in results:
                if doctor.available_slots:
                    booked_slots = {}
                    # Get all appointments for this doctor on their available dates
                    appointments = Appointment.query.filter(
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date.cast(db.Date).in_(doctor.available_slots.keys()),
                        Appointment.status.in_(['Pending', 'Confirmed'])
                    ).all()
                    for appt in appointments:
                        appt_date_str = appt.appointment_date.strftime('%Y-%m-%d')
                        appt_time_str = appt.appointment_date.strftime('%H:%M')
                        if appt_date_str in doctor.available_slots and appt_time_str in doctor.available_slots[appt_date_str]:
                            doctor.available_slots[appt_date_str].remove(appt_time_str)

            recent_searches = (
                SearchHistory.query.filter_by(patient_id=session["patient_id"])
                .order_by(SearchHistory.id.desc())
                .limit(5)
                .all())
        return render_template('doctor_finding.html', doctors=results, recent_searches=recent_searchs)
    
    @app.route("/about")
    def about():
        return render_template("about.html")
    
    @app.route("/contactus")
    def contactus():
        return render_template("contactus.html")
    
    @app.route("/services")
    def services():
        return render_template("services.html")
    
    # Hospital Services
    @app.route('/hospital_finding')
    @login_required
    def hospital_finder():
        return render_template('hospital_finder.html')
    
    @app.route("/user_profile", methods=["GET", "POST"])
    def user_profile():
        if "patient_id" not in session:
            flash("Please login first!", "danger")
            return redirect(url_for("login"))

        patient = Patient.query.get(session["patient_id"])

        if request.method == "POST":
            # Update text fields
            patient.name = request.form.get("name", patient.name)
            patient.mobile = request.form.get("mobile", patient.mobile)
            patient.email = request.form.get("email", patient.email)
            patient.location = request.form.get("location", patient.location)
            patient.bio = request.form.get("bio", patient.bio)

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