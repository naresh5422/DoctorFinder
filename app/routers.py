from flask import render_template, request, session, redirect, url_for, flash, jsonify, current_app
from app.services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist, find_hospitals, get_featured_hospitals, extract_entities_from_query, get_autocomplete_suggestions, get_location_suggestions
import os
import random
from werkzeug.utils import secure_filename
from app.extension import db, mail, login_required, check_gmail_app_password
from app.models import SearchHistory, Patient, Doctor, Appointment, Review, Message
from datetime import datetime, date
from sqlalchemy import func, case, and_
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_mail import Message as MailMessage  # Alias to avoid name conflict with model
from firebase_admin import auth
import smtplib
from markupsafe import Markup


def _filter_doctor_slots(doctors_list):
    """
    A helper function to filter a list of doctors' available_slots.
    It removes past slots and already booked slots. This version is optimized
    to avoid making a separate database query for each doctor (N+1 problem).
    """
    if not doctors_list:
        return doctors_list

    today = date.today()
    now = datetime.now()

    doctor_ids = [doc.id for doc in doctors_list]
    all_slot_dates = set()
    for doc in doctors_list:
        if isinstance(doc.available_slots, dict):
            all_slot_dates.update(doc.available_slots.keys())

    # If no doctors have any slots defined, we can just clear them and return.
    if not all_slot_dates:
        for doc in doctors_list:
            doc.available_slots = {}
        return doctors_list

    # --- Optimized Appointment Fetching ---
    # Fetch all relevant appointments for all doctors in the list in a single query.
    all_appointments = Appointment.query.filter(
        Appointment.doctor_id.in_(doctor_ids),
        Appointment.appointment_date.cast(db.Date).in_(all_slot_dates),
        Appointment.status.in_(['Pending', 'Confirmed'])
    ).all()

    # Create a lookup map for booked slots: {doctor_id: {booked_slot_key, ...}}
    booked_slots_by_doctor = {}
    for appt in all_appointments:
        slot_key = f"{appt.appointment_date.strftime('%Y-%m-%d')}_{appt.appointment_date.strftime('%H:%M')}"
        booked_slots_by_doctor.setdefault(appt.doctor_id, set()).add(slot_key)
    # --- End Optimization ---

    for doctor in doctors_list:
        if not isinstance(doctor.available_slots, dict):
            doctor.available_slots = {}
            continue
        
        valid_slots = {}
        booked_slot_times = booked_slots_by_doctor.get(doctor.id, set())

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
        # Order by rating to show top-rated doctors.
        featured_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        _filter_doctor_slots(featured_doctors) # Ensure slots shown are valid
        return render_template("index.html", featured_doctors=featured_doctors)

    @app.route("/home")
    @login_required
    def patient_home():
        patient = Patient.query.get(session['patient_id'])
        # Fetch top-rated doctors to display on the patient's homepage
        top_doctors = Doctor.query.order_by(Doctor.rating.desc()).limit(3).all()
        _filter_doctor_slots(top_doctors)
        return render_template("patient_home.html", patient=patient, top_doctors=top_doctors)
    
    @app.route('/browse_doctors')
    def browse_doctors():
        """
        Displays all doctors, paginated and sorted by availability, review count, and rating.
        This page is now public and does not require login.
        """
        page = request.args.get('page', 1, type=int)

        # Subquery to get the review count for each doctor, which we'll use for sorting.
        review_count_subq = db.session.query(
            Review.doctor_id,
            func.count(Review.id).label('review_count')
        ).group_by(Review.doctor_id).subquery()

        # Create a CASE statement to prioritize doctors with available slots.
        # This is a simple check: if the `available_slots` field is not NULL and not an empty JSON object '{}'.
        # Doctors with slots get priority 0, others get 1.
        has_slots_case = case(
            (and_(Doctor.available_slots != None, Doctor.available_slots != {}), 0),
            else_=1
        )

        # Query to fetch doctors, joining with review counts.
        # We sort by availability first, then by review count and rating.
        all_doctors_query = Doctor.query.outerjoin(
            review_count_subq, Doctor.id == review_count_subq.c.doctor_id
        ).order_by(
            has_slots_case.asc(), # Doctors with slots (priority 0) come first.
            func.coalesce(review_count_subq.c.review_count, 0).desc(),
            Doctor.rating.desc()
        )

        # Paginate the results, showing 10 doctors per page.
        pagination = all_doctors_query.paginate(page=page, per_page=10, error_out=False)
        all_doctors_list = pagination.items

        # Filter slots to show only valid, available ones
        _filter_doctor_slots(all_doctors_list)

        # Fetch recent searches for the sidebar (only if a user is logged in)
        recent_searches = []
        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()

        return render_template('doctor_finding.html', doctors=all_doctors_list, recent_searches=recent_searches, 
                               datetime=datetime, disease_query="", location_query="",
                               pagination=pagination, page_title="Browse All Doctors")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        patient_id = session["patient_id"]
        now = datetime.now()
        
        # Fetch counts for stats directly from the database for efficiency.
        # Refined total: Exclude expired pending appointments as they are non-events.
        total_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            db.or_(
                Appointment.status != 'Pending',
                Appointment.appointment_date > now
            )
        ).count()
        
        pending_appointments_count = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Pending',
            Appointment.appointment_date > now
        ).count()
        
        confirmed_appointments_count = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Confirmed',
            Appointment.appointment_date > now
        ).count()
        
        # Count unique doctors for completed consultations
        consultations_completed_count = db.session.query(func.count(func.distinct(Appointment.doctor_id))).filter(
            Appointment.user_id == patient_id,
            Appointment.status == 'Completed'
        ).scalar() or 0

        # Fetch reviews given by the patient
        reviews_given = Review.query.filter_by(patient_id=patient_id).order_by(Review.timestamp.desc()).all()

        # --- New: Count unique conversations ---
        # A conversation exists if there's an appointment or a message.
        appointment_doctor_ids = db.session.query(Appointment.doctor_id).filter_by(user_id=patient_id).distinct()
        message_doctor_ids = db.session.query(Message.doctor_id).filter_by(patient_id=patient_id).distinct()
        conversation_doctor_ids = {row[0] for row in appointment_doctor_ids.union(message_doctor_ids).all()}
        total_conversations_count = len(conversation_doctor_ids)

        recent_searches = SearchHistory.query.filter_by(patient_id=patient_id).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter(
            Appointment.user_id == patient_id,
            Appointment.status.in_(['Pending', 'Confirmed']),
            Appointment.appointment_date >= now
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
        now = datetime.now()
        
        appointments_query = Appointment.query.filter_by(user_id=patient_id)

        # --- Refactored Appointment Filtering ---
        # This logic now filters out expired appointments from the 'Pending' and 'Confirmed'
        # views to provide a cleaner and more relevant appointment list.
        if status_filter in ['Pending', 'Confirmed']:
            # For Pending and Confirmed tabs, only show upcoming appointments.
            appointments_query = appointments_query.filter(
                Appointment.status == status_filter,
                Appointment.appointment_date > now
            )
        elif status_filter in ['Completed', 'Canceled']:
            # For Completed and Cancelled tabs, show all historical appointments.
            appointments_query = appointments_query.filter_by(status=status_filter)
        else: # No status filter (the "All" tab)
            pass # The base query fetches all appointments, which is correct for the "All" tab.

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

        return render_template('my_appointments.html', appointments=appointments, reviewed_doctor_ids=reviewed_doctor_ids, conversations=conversations, status_filter=status_filter, view_filter=view_filter, now=now)

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
            text=comment
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

        disease_query = search.disease
        location_query = search.location

        # The main search bar should show the original query.
        # The location bar is not used on the results page for repeated searches.
        location_query = "" # Clear this to avoid it being appended in the template

        mapping_result = map_disease_to_specialist(disease_query)
        specialist = mapping_result["specialist"]
        results = []

        if specialist:
            all_nearby_locations = set()
            # The saved location can be a comma-separated string of multiple locations
            search_locations = [loc.strip() for loc in search.location.split(',')]
            for loc in search_locations:
                if loc:
                    nearby = get_nearby_locations(loc)
                    all_nearby_locations.update(nearby)

            query = Doctor.query.filter(Doctor.specialization == specialist)
            if all_nearby_locations:
                query = query.filter(Doctor.location.in_(list(all_nearby_locations)))
            
            results = query.order_by(Doctor.rating.desc()).all()

            if not results:
                flash(f"We understood you're looking for a '{specialist}', but we couldn't find any in '{search.location}' or nearby areas. You could try a new search.", "info")
        else:
            flash(f"We couldn't identify a specialty for '{disease_query}'. Please try another search.", "warning")

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
        final_locations = []
        final_symptom = ""

        # If the find_doctor page is accessed directly via GET without any search parameters,
        # it's likely the user wants to browse all doctors. Redirect them to the correct page.
        if request.method == "GET" and not request.args:
            return redirect(url_for('browse_doctors'))

        if request.method == "POST":
            location_input = request.form.get("location", "").strip()
            disease_input = request.form.get("disease", "").strip()

            # --- AI-powered Query Processing ---
            # 1. Use NER on the disease/symptom field to see if it contains a location.
            # This handles queries like "heart pain in Kurnool" in a single input box.
            entities = extract_entities_from_query(disease_input)
            
            final_symptom = entities['symptom']
            extracted_locations = entities['locations']

            # 2. Decide on the final locations. Combine dedicated input and extracted locations.
            final_locations = []
            if location_input:
                # A user might enter "Hyderabad, Tirupati" in the location box
                final_locations.extend([loc.strip() for loc in location_input.split(',')])
            if extracted_locations:
                final_locations.extend(extracted_locations)
            
            # Remove duplicates and empty strings, preserving order
            final_locations = list(dict.fromkeys(filter(None, final_locations)))
            
            # Set variables for displaying in the search bars on the results page.
            disease_query = disease_input
            location_query = location_input

            # Save search to database for POST requests if user is logged in
            if final_locations and disease_input and 'patient_id' in session:
                search = SearchHistory(patient_id=session["patient_id"],
                                       location=", ".join(final_locations), # Store as comma-separated string
                                       disease=disease_input) # Save original query for history
                db.session.add(search)
                db.session.commit()
        
        elif request.method == "GET" and 'disease' in request.args:
            # This handles clicks on specialty cards, e.g., /find_doctor?disease=Cardiologist
            final_symptom = request.args.get('disease')
            disease_query = final_symptom
            # Location is not provided by default when browsing by specialty.
            final_locations = []
            location_query = ""
            # The flash message is removed as we now support specialty-only searches.

        # --- Flexible Search Logic ---
        # This logic handles searches by symptom, location, or both.
        query = Doctor.query
        specialist = None
        
        # Only proceed with a search if there's something to search for.
        if not final_symptom and not final_locations:
            if request.method == "POST":
                flash("Please enter a symptom, specialty, or location to search.", "info")
        else:
            # 1. Filter by symptom/specialty if provided
            if final_symptom:
                mapping_result = map_disease_to_specialist(final_symptom)
                specialist = mapping_result["specialist"]
                did_you_mean = mapping_result["did_you_mean"]

                if did_you_mean:
                    flash(f"Showing results for '{did_you_mean}', as no exact match was found for '{disease_query}'.", "info")

                if specialist:
                    query = query.filter(Doctor.specialization == specialist)
                else:
                    # If a symptom was provided but no specialty was found, return no results.
                    flash(f"We couldn't identify a specific medical specialty for '{final_symptom}'. Please try rephrasing your search.", "warning")
                    query = query.filter(False) # Effectively returns no results

            # 2. Filter by location if provided
            if final_locations:
                all_nearby_locations = set()
                for loc in final_locations:
                    nearby = get_nearby_locations(loc.strip())
                    all_nearby_locations.update(nearby)
                
                if all_nearby_locations:
                    query = query.filter(Doctor.location.in_(list(all_nearby_locations)))
            
            # 3. Execute the query and get results
            results = query.order_by(Doctor.rating.desc()).all()
            
            # 4. Provide feedback if no results were found
            if not results and (final_symptom or final_locations):
                feedback_parts = []
                if specialist: feedback_parts.append(f"a '{specialist}'")
                elif final_symptom: feedback_parts.append(f"'{final_symptom}'")
                if final_locations: feedback_parts.append(f"in '{', '.join(final_locations)}' or nearby areas")
                if feedback_parts:
                    flash(f"We couldn't find any doctors for {' and '.join(feedback_parts)}. You could try a new search.", "info")

            _filter_doctor_slots(results)

        if 'patient_id' in session:
            recent_searches = SearchHistory.query.filter_by(patient_id=session["patient_id"]).order_by(SearchHistory.id.desc()).limit(5).all()
        
        return render_template('doctor_finding.html', doctors=results, recent_searches=recent_searches, datetime=datetime,
                               disease_query=disease_query, location_query=location_query)
    
    @app.route('/autocomplete')
    def autocomplete():
        """
        Provides real-time search suggestions for the main search bar.
        """
        query = request.args.get('q', '').strip()
        # Don't return suggestions for very short queries to avoid too much noise.
        if len(query) < 2:
            return jsonify([])
        suggestions = get_autocomplete_suggestions(query)
        return jsonify(suggestions)

    @app.route('/autocomplete/location')
    def autocomplete_location():
        """
        Provides real-time search suggestions for location input fields.
        """
        query = request.args.get('q', '').strip()
        # Allow shorter queries for location aliases like 'hyd'
        if len(query) < 1:
            return jsonify([])
        suggestions = get_location_suggestions(query)
        return jsonify(suggestions)

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
        # Check if mail is configured before attempting to send.
        is_mail_configured = all([current_app.config.get('MAIL_SERVER'), current_app.config.get('MAIL_USERNAME'), current_app.config.get('MAIL_PASSWORD')])

        if not is_mail_configured:
            # This case is primarily handled by the template disabling the button,
            # but this server-side check is a good fallback.
            flash("The email service is not configured. Please contact support.", "danger")
            return redirect(url_for('user_profile'))

        if not check_gmail_app_password():
            return redirect(url_for('user_profile'))

        patient = Patient.query.get(session['patient_id'])
        if not patient.email:
            flash('Please add an email address to your profile first.', 'warning')
            return redirect(url_for('user_profile'))

        if hasattr(patient, 'email_verified') and patient.email_verified:
            flash('Your email is already verified.', 'info')
            return redirect(url_for('user_profile'))

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        session['email_verification_otp'] = otp
        session['email_to_verify'] = patient.email

        # Send email with OTP
        msg = MailMessage('Verify Your Email for CareConnect',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[patient.email])
        msg.body = f'Your CareConnect email verification OTP is: {otp}'
        try:
            mail.send(msg)
            flash(f'An OTP has been sent to {patient.email}. Please check your inbox.', 'info')
        except smtplib.SMTPAuthenticationError as e:
            error_msg = Markup("Email sending failed due to an authentication error. If using Gmail, please use a 16-character <strong>App Password</strong>. <a href='https://myaccount.google.com/apppasswords' target='_blank' class='alert-link'>Generate one here</a>.")
            flash(error_msg, "danger")
            current_app.logger.error(f"SMTPAuthenticationError: {e}. Check MAIL_USERNAME and MAIL_PASSWORD.")
            if current_app.debug:
                flash(Markup(f"DEV MODE: Email sending failed. You can <a href='{url_for('dev_bypass_patient_email_verification')}' class='alert-link'>click here to bypass verification</a>."), 'info')
            return redirect(url_for('user_profile'))

        return redirect(url_for('verify_email_otp'))

    @app.route('/verify_email_otp', methods=['GET', 'POST'])
    @login_required
    def verify_email_otp():
        if 'email_verification_otp' not in session:
            flash('Verification process has expired. Please try again.', 'warning')
            return redirect(url_for('user_profile'))

        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('email_verification_otp'):
                patient = Patient.query.get(session['patient_id'])
                if patient.email == session.get('email_to_verify'):
                    patient.email_verified = True
                    db.session.commit()
                    flash('Your email has been successfully verified!', 'success')
                    # Clean up session
                    session.pop('email_verification_otp', None)
                    session.pop('email_to_verify', None)
                    return redirect(url_for('user_profile'))
                else:
                    flash('Email address has changed. Please restart verification.', 'danger')
                    return redirect(url_for('user_profile'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        
        return render_template('patient_verify_email.html')

    @app.route('/verify_phone_token', methods=['POST'])
    @login_required
    def verify_phone_token():
        """
        Verifies a Firebase Auth ID token sent from the client after successful
        phone number OTP verification.
        """
        id_token = request.json.get('token')
        if not id_token:
            return jsonify({'success': False, 'error': 'No token provided.'}), 400

        try:
            # Verify the ID token is valid and not revoked.
            decoded_token = auth.verify_id_token(id_token)
            firebase_phone_number = decoded_token.get('phone_number')

            patient = Patient.query.get(session['patient_id'])

            # Ensure the number from the token matches the number in the user's profile.
            # Firebase numbers are in E.164 format (e.g., +919876543210).
            if patient.mobile == firebase_phone_number:
                patient.mobile_verified = True
                db.session.commit()
                flash('Your mobile number has been successfully verified!', 'success')
                return jsonify({'success': True})
            else:
                error_msg = f'Verified number ({firebase_phone_number}) does not match your profile number ({patient.mobile}). Please update your profile and try again.'
                return jsonify({'success': False, 'error': error_msg}), 400

        except auth.InvalidIdTokenError:
            return jsonify({'success': False, 'error': 'The provided token is invalid.'}), 401
        except Exception as e:
            current_app.logger.error(f"Firebase token verification failed for patient {session['patient_id']}: {e}")
            return jsonify({'success': False, 'error': 'An internal server error occurred during verification.'}), 500

    @app.route('/dev/bypass_patient_mobile_verification')
    @login_required
    def dev_bypass_patient_mobile_verification():
        """
        A developer-only route to bypass mobile verification without Firebase.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        patient = Patient.query.get(session['patient_id'])
        patient.mobile_verified = True
        db.session.commit()
        flash('DEV MODE: Mobile number verification bypassed.', 'success')
        return redirect(url_for('user_profile'))

    @app.route('/dev/bypass_patient_email_verification')
    @login_required
    def dev_bypass_patient_email_verification():
        """
        A developer-only route to bypass email verification without sending an email.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        patient = Patient.query.get(session['patient_id'])
        patient.email_verified = True
        db.session.commit()
        flash('DEV MODE: Email verification bypassed.', 'success')
        return redirect(url_for('user_profile'))

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