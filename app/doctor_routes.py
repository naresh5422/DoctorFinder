import os
import json
import random
from flask import render_template, request, session, redirect, url_for, flash, current_app, Markup
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_mail import Message as MailMessage  # Alias to avoid name conflict with model
from twilio.rest import Client
from datetime import date, datetime, timedelta
import smtplib
from firebase_admin import auth
from app.extension import db, mail, doctor_login_required, doctor_verified_required, check_gmail_app_password
from app.models import Doctor, Review, Appointment, Message, Patient, Prescription 
from werkzeug.utils import secure_filename
from sqlalchemy import func

def setup_doctor_routes(app):
    # Doctor Services
    @app.route('/doctor')
    def doctor_home():
        if 'doctor_id' in session:
            return redirect(url_for('doctor_dashboard'))
        return redirect(url_for('doctor_login'))

    @app.context_processor
    def inject_doctor_data():
        context = {'doctor_details': None, 'unread_doctor_messages': 0}
        if 'doctor_id' in session:
            context['doctor_details'] = session.get('doctor_details')
            context['unread_doctor_messages'] = Message.query.filter_by(
                doctor_id=session['doctor_id'],
                sender_type='patient',
                is_read=False
            ).count()
        return context


    @app.route('/doctor_profile', methods = ['GET','POST'])
    def doctor_profile():
        doctors = []
        doctor_name_query = ""
        is_review_submission = "review_text" in request.form and "doctor_id" in request.form

        if request.method == 'POST':
            if is_review_submission:
                doctor_id_str = request.form.get("doctor_id", "").strip()
                doctor_id = int(doctor_id_str) if doctor_id_str.isdigit() else None
                review_text = request.form["review_text"].strip()
                rating = int(request.form.get("rating", 5))
                patient_id = session.get('patient_id')

                if not all([doctor_id, review_text, patient_id]):
                    flash("Invalid review submission.", "danger")
                    return redirect(request.args.get('next') or url_for("doctor_profile"))
                
                # Security Check: A patient can only review a doctor after a completed appointment.
                can_review = Appointment.query.filter_by(
                    doctor_id=doctor_id,
                    user_id=patient_id,
                    status='Completed'
                ).first()

                if not can_review:
                    flash("You can only review a doctor after a completed appointment.", "danger")
                    return redirect(request.args.get('next') or url_for("doctor_profile"))
                
                # Prevent duplicate reviews
                if Review.query.filter_by(doctor_id=doctor_id, patient_id=patient_id).first():
                    flash("You have already submitted a review for this doctor.", "warning")
                    return redirect(request.args.get('next') or url_for("doctor_profile"))

                # All checks passed, add the review
                new_review = Review(text=review_text, rating=rating, doctor_id=doctor_id, patient_id=patient_id)
                db.session.add(new_review)

                # Recalculate doctor's average rating
                doctor = Doctor.query.get(doctor_id)
                if doctor:
                    all_reviews = Review.query.filter_by(doctor_id=doctor_id).all()
                    total_ratings = sum(r.rating for r in all_reviews)
                    average_rating = total_ratings / len(all_reviews) if all_reviews else 0
                    doctor.rating = round(average_rating, 1)

                db.session.commit()
                flash("Your review has been submitted.", "success")
                
                # Redirect back to the 'next' URL if provided, otherwise default to the doctor profile page.
                # This ensures the user returns to the page they were on (e.g., My Appointments).
                next_url = request.args.get('next') or url_for("doctor_profile")
                return redirect(next_url)
            else:
                # This is for the doctor search form on the profile page itself
                doctor_name_query = request.form.get('doctor_name', '').strip()
                if doctor_name_query:
                    doctors = Doctor.query.filter(Doctor.doctor_name.ilike(f'%{doctor_name_query}%')).all()
        
        # For GET requests with a query parameter
        elif 'doctor_name' in request.args:
            doctor_name_query = request.args.get('doctor_name', '')
            doctors = Doctor.query.filter(Doctor.doctor_name.ilike(f'%{doctor_name_query}%')).all() if doctor_name_query else []

        # For each doctor, check if the logged-in patient has a completed appointment
        if 'patient_id' in session and doctors:
            patient_id = session['patient_id']
            for doc in doctors:
                completed_appointment = Appointment.query.filter_by(
                    doctor_id=doc.id,
                    user_id=patient_id,
                ).filter(Appointment.status == 'Completed').first()
                doc.can_be_reviewed_by_user = completed_appointment is not None
        else:
            for doc in doctors:
                doc.can_be_reviewed_by_user = False
            
        return render_template('doctor_profile.html', doctors=doctors, doctor_name=doctor_name_query)

    @app.route("/my_profile", methods=["GET"])
    def my_profile():
        if "doctor_id" not in session:
            flash("Please login first", "warning")
            return redirect(url_for("doctor_login"))
        # Fetch from DB to get the most up-to-date info, including verification status
        doctor = Doctor.query.get(session['doctor_id'])
        if not doctor:
            flash("Doctor profile not found. Please log in again.", "danger")
            return redirect(url_for("doctor_login"))
        return render_template("my_profile.html", doctor=doctor)

    @app.route("/doctor_register", methods=["GET", "POST"])
    def doctor_register():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")
            doctor_name = request.form.get("name")
            specialization = request.form.get("specialization")
            mobile_no = request.form.get("mobile")
            email_id = request.form.get("email")
            location = request.form.get("location")
            hospital_name = request.form.get("hospital_name")

            # Validate required fields
            if not all([username, password, doctor_name, specialization, mobile_no, email_id, location, hospital_name]):
                flash("Please fill all required fields", "danger")
                return redirect(url_for("doctor_register"))
            
            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("doctor_register"))

            # Check for duplicate username in the database
            if Doctor.query.filter_by(username=username).first():
                flash("Username already exists. Please choose another one.", "danger")
                return redirect(url_for("doctor_register"))

            # Create new Doctor object
            new_doctor = Doctor(
                username=username,
                doctor_name=doctor_name,
                specialization=specialization,
                mobile_no=mobile_no,
                email_id=email_id,
                location=location,
                hospital_name=hospital_name,
                hospital_address=request.form.get("hospital_address"),
                hospital_contact=request.form.get("hospital_contact"),
                experience=int(request.form.get("experience", 0)),
                bio=request.form.get("bio"),
                education=request.form.get("education"),
                certifications=request.form.get("certifications"),
                available_slots={}
            )
            new_doctor.set_password(password) # Hash the password

            db.session.add(new_doctor)
            db.session.commit()

            flash("Doctor registered successfully!", "success")
            return redirect(url_for("doctor_login"))

        return render_template("doctor_registration.html")

    @app.route("/doctor_login", methods=["GET", "POST"])
    def doctor_login():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"].strip()

            # Query the database for the doctor
            doctor = Doctor.query.filter_by(username=username).first()

            # The check_password method correctly handles hashed passwords.
            # For backward compatibility with unhashed passwords from initial data load,
            if doctor and doctor.check_password(password):
                session['doctor_id'] = doctor.id
                session['doctor_name'] = doctor.doctor_name
                # Store doctor details in session for easy access
                session['doctor_details'] = {
                    "id": doctor.id,
                    "doctor_name": doctor.doctor_name,
                    "specialization": doctor.specialization,
                    "mobile_no": doctor.mobile_no,
                    "email_id": doctor.email_id,
                    "location": doctor.location,
                    "experience": doctor.experience,
                    "hospital_name": doctor.hospital_name,
                    "hospital_address": doctor.hospital_address,
                    "hospital_contact": doctor.hospital_contact,
                    "bio": doctor.bio,
                    "education": doctor.education,
                    "certifications": doctor.certifications,
                    "available_slots": doctor.available_slots,
                    "image": doctor.image,
                    "email_verified": getattr(doctor, 'email_verified', False),
                    "mobile_verified": getattr(doctor, 'mobile_verified', False)
                }
                flash("Login successful!", "success")
                return redirect(url_for("doctor_home_page"))
            else:
                flash("Invalid username or password. If you don't have an account, please register.", "danger")
        return render_template("doctor_login.html")

    @app.route("/doctor/forgot_password", methods=['GET', 'POST'])
    def doctor_forgot_password():
        if request.method == 'POST':
            identifier = request.form.get('identifier').strip()
            
            # Check if identifier is an email or a mobile number
            if '@' in identifier:
                doctor = Doctor.query.filter_by(email_id=identifier).first()
            else:
                doctor = Doctor.query.filter_by(mobile_no=identifier).first()

            if doctor:
                # Generate a secure token
                s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
                token = s.dumps(doctor.id, salt='password-reset-salt')

                if '@' in identifier:
                    # --- BEGIN REFACTOR ---
                    # More detailed check for email configuration.
                    missing_vars = []
                    required_vars = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD']
                    for var in required_vars:
                        if not current_app.config.get(var):
                            missing_vars.append(var)
                    if missing_vars:
                        error_msg = f"Email feature disabled: The mail server is not configured. To enable this, please set the following in your .env file: {', '.join(missing_vars)}. See README.md for examples."
                        flash(error_msg, 'danger')
                        current_app.logger.error(f"Password reset failed: Missing environment variables: {', '.join(missing_vars)}")
                        return redirect(url_for('doctor_forgot_password'))
                    # --- END REFACTOR ---
                    if not check_gmail_app_password():
                        return redirect(url_for('doctor_forgot_password'))

                    # Send a real email
                    reset_url = url_for('doctor_reset_with_token', token=token, _external=True)
                    msg = MailMessage('Password Reset Request',
                                  sender=app.config['MAIL_USERNAME'],
                                  recipients=[doctor.email_id])
                    msg.body = f'''To reset your password, visit the following link:
{reset_url}
If you did not make this request then simply ignore this email and no changes will be made.'''
                    try:
                        mail.send(msg)
                        flash(f"A password reset link has been sent to {doctor.email_id}.", "info")
                    except smtplib.SMTPAuthenticationError as e:
                        error_msg = Markup("Email sending failed due to an authentication error. If using Gmail, please use a 16-character <strong>App Password</strong>. <a href='https://myaccount.google.com/apppasswords' target='_blank' class='alert-link'>Generate one here</a>.")
                        flash(error_msg, "danger")
                        current_app.logger.error(f"SMTPAuthenticationError: {e}. Check MAIL_USERNAME and MAIL_PASSWORD.")
                        return redirect(url_for('doctor_forgot_password'))

                else:
                    # Generate a random 6-digit OTP
                    otp = str(random.randint(100000, 999999))
                    session['reset_otp'] = otp
                    session['reset_doctor_id'] = doctor.id

                    # --- BEGIN REFACTOR ---
                    # More detailed check for Twilio configuration.
                    missing_vars = []
                    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']
                    for var in required_vars:
                        if not current_app.config.get(var):
                            missing_vars.append(var)
                    if missing_vars:
                        error_msg = f"SMS feature disabled: The SMS service is not configured. To enable this, please set the following in your .env file: {', '.join(missing_vars)}. See README.md for examples."
                        flash(error_msg, 'danger')
                        current_app.logger.error(f"Password reset failed: Missing Twilio environment variables: {', '.join(missing_vars)}")
                        return redirect(url_for('doctor_forgot_password'))
                    # --- END REFACTOR ---

                    # Send the OTP via Twilio
                    try:
                        client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])
                        message = client.messages.create(
                            body=f"Your password reset OTP for CareConnect is: {otp}",
                            from_=app.config['TWILIO_PHONE_NUMBER'],
                            to=doctor.mobile_no # Ensure this includes the country code, e.g., +1234567890
                        )
                        flash(f"An OTP has been sent to your mobile number.", "info")
                    except Exception as e:
                        flash("Failed to send OTP. Please check your mobile number or try again later.", "danger")
                        # More detailed logging for debugging
                        print(f"Twilio Error: {e}")
                        app.logger.error(f"Twilio failed to send SMS: {e}")
                        return redirect(url_for('doctor_forgot_password'))

                    return redirect(url_for('doctor_verify_otp'))
            else:
                flash("No account found with that email or mobile number.", "danger")
            
            return redirect(url_for('doctor_login'))

        return render_template("doctor_forgot_password.html")

    @app.route('/doctor/verify_otp', methods=['GET', 'POST'])
    def doctor_verify_otp():
        if 'reset_doctor_id' not in session:
            flash("Please start the password reset process again.", "warning")
            return redirect(url_for('doctor_forgot_password'))

        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('reset_otp'):
                # OTP is correct, allow password reset.
                session['otp_verified'] = True # Set a flag
                return redirect(url_for('doctor_reset_with_token', token='use-otp'))
            else:
                flash("Invalid OTP. Please try again.", "danger")

        return render_template('doctor_verify_otp.html')


    @app.route('/doctor/reset/<token>', methods=['GET', 'POST'])
    def doctor_reset_with_token(token):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        
        if request.method == 'POST':
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for('doctor_reset_with_token', token=token))
            
            # Logic for OTP-based reset
            if token == 'use-otp':
                # Check if OTP was verified in the previous step
                if session.get('otp_verified'):
                    doctor = Doctor.query.get(session['reset_doctor_id'])
                    doctor.set_password(password)
                    db.session.commit()
                    # Clean up session variables
                    session.pop('reset_otp', None); session.pop('reset_doctor_id', None); session.pop('otp_verified', None)
                    flash('Your password has been updated!', 'success')
                    return redirect(url_for('doctor_login'))
                else:
                    flash('OTP not verified. Please complete the verification step.', 'danger')
                    return redirect(url_for('doctor_forgot_password'))
            
            # Logic for email token-based reset
            try:
                doctor_id = s.loads(token, salt='password-reset-salt', max_age=3600) # 1-hour expiry
                doctor = Doctor.query.get(doctor_id)
                doctor.set_password(password)
                db.session.commit()
                flash('Your password has been updated!', 'success')
                return redirect(url_for('doctor_login'))
            except (SignatureExpired, BadTimeSignature):
                flash('The password reset link is invalid or has expired.', 'danger')
                return redirect(url_for('doctor_forgot_password'))

        return render_template('doctor_reset_password.html', token=token, otp_method=(token == 'use-otp'))

    @app.route("/doctor_dashboard")
    def doctor_dashboard():
        if "doctor_id" not in session:
            flash("Please log in as doctor to continue.", "danger")
            return redirect(url_for("doctor_login"))
        doctor_id = session["doctor_id"] 
        doctor_session_details = session.get('doctor_details')

        if not doctor_session_details:
            flash("Doctor profile not found.", "danger")
            return redirect(url_for("doctor_login"))
        
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            flash("Doctor database record not found.", "danger")
            return redirect(url_for("doctor_login"))

        # Appointments are still fetched from the database
        all_appointments = Appointment.query.filter_by(doctor_id=doctor_id).order_by(Appointment.appointment_date.desc()).all()

        pending_appointments = [a for a in all_appointments if a.status == 'Pending']
        confirmed_appointments = [a for a in all_appointments if a.status == 'Confirmed']
        completed_appointments = [a for a in all_appointments if a.status == 'Completed']

        # --- Start: Logic to get recent conversations for dashboard ---
        # Subquery to get the last message for each patient conversation
        subq = db.session.query(
            Message.patient_id,
            func.max(Message.timestamp).label('max_ts')
        ).filter(Message.doctor_id == doctor_id).group_by(Message.patient_id).subquery()

        # Join to get the full last message details, order by most recent, and limit
        last_messages_q = db.session.query(Message).join(
            subq,
            db.and_(Message.patient_id == subq.c.patient_id, Message.timestamp == subq.c.max_ts)
        ).order_by(subq.c.max_ts.desc()).limit(5)
        
        recent_conversations = []
        for msg in last_messages_q.all():
            patient = Patient.query.get(msg.patient_id)
            # Count unread messages from this patient
            unread_count = Message.query.filter_by(
                doctor_id=doctor_id, 
                patient_id=patient.id, 
                is_read=False, 
                sender_type='patient'
            ).count()
            recent_conversations.append({
                'patient': patient,
                'last_message': msg,
                'unread_count': unread_count
            })
        # --- End: Logic for recent conversations ---
        
        # --- New: Get recent reviews ---
        recent_reviews = Review.query.filter_by(doctor_id=doctor_id).order_by(Review.timestamp.desc()).limit(3).all()

        # --- New: Get slots for the next 7 days ---
        today = date.today()
        now = datetime.now()
        weekly_slots = {}

        # Robustly handle available_slots which might be a string from old data
        current_slots = doctor.available_slots
        if isinstance(current_slots, str):
            try:
                current_slots = json.loads(current_slots)
            except json.JSONDecodeError:
                current_slots = {}

        if current_slots:
            # Sort the dates first to process them in order
            sorted_dates = sorted(current_slots.keys())
            for date_str in sorted_dates:
                try:
                    slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if today <= slot_date < today + timedelta(days=7):
                        # Filter out past times for today's date
                        if slot_date == today:
                            future_times = [
                                time_str for time_str in current_slots[date_str]
                                if datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M') > now
                            ]
                            if future_times:
                                weekly_slots[date_str] = future_times
                        else: # For future dates, all slots are valid
                            weekly_slots[date_str] = current_slots[date_str]
                except ValueError:
                    continue # Ignore invalid date keys

        return render_template("doctor_dashboard.html", doctor=doctor_session_details,
                               pending_appointments=pending_appointments,
                               confirmed_appointments=confirmed_appointments,
                               completed_appointments=completed_appointments,
                               datetime=datetime,
                               recent_conversations=recent_conversations,
                               recent_reviews=recent_reviews,
                               weekly_slots=weekly_slots)

    @app.route("/doctor/home")
    def doctor_home_page():
        if "doctor_id" not in session:
            flash("Please log in to access your homepage.", "warning")
            return redirect(url_for("doctor_login"))
        doctor_name = session.get("doctor_name", "Doctor")
        return render_template("doctor_home.html", doctor_name=doctor_name)

    @app.route("/doctor_logout")
    def doctor_logout():
        session.pop("doctor_id", None)
        session.pop("doctor_username", None)
        session.pop("doctor_name", None)
        session.pop("doctor_details", None)
        flash("You have been logged out successfully.", "info")
        return redirect(url_for("doctor_home"))

    @app.route("/doctor/edit_profile", methods=['GET', 'POST'])
    def edit_doctor_profile():
        if "doctor_id" not in session:
            flash("Please login to edit your profile.", "warning")
            return redirect(url_for("doctor_login"))

        # Fetch the doctor from the database to get the most up-to-date info,
        # including verification status.
        doctor_to_update = Doctor.query.get(session['doctor_id'])
        if not doctor_to_update:
            flash("Could not find your profile in the database.", "danger")
            return redirect(url_for('doctor_login'))

        if request.method == 'POST':
            # Update general fields
            doctor_to_update.doctor_name = request.form.get('doctor_name', doctor_to_update.doctor_name)
            doctor_to_update.specialization = request.form.get('specialization')

            # Only update email/mobile if they are not verified
            if not (hasattr(doctor_to_update, 'email_verified') and doctor_to_update.email_verified):
                doctor_to_update.email_id = request.form.get('email_id', doctor_to_update.email_id)
            
            if not (hasattr(doctor_to_update, 'mobile_verified') and doctor_to_update.mobile_verified):
                doctor_to_update.mobile_no = request.form.get('mobile_no', doctor_to_update.mobile_no)

            doctor_to_update.location = request.form.get('location')
            doctor_to_update.experience = int(request.form.get('experience', 0))
            doctor_to_update.hospital_name = request.form.get('hospital_name')
            doctor_to_update.hospital_address = request.form.get('hospital_address')
            doctor_to_update.hospital_contact = request.form.get('hospital_contact')
            doctor_to_update.bio = request.form.get('bio')
            doctor_to_update.education = request.form.get('education')
            doctor_to_update.certifications = request.form.get('certifications')
            
            # Handle profile image upload
            if "image" in request.files:
                file = request.files["image"]
                if file and file.filename != "":
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(filepath)
                    doctor_to_update.image = f"uploads/{filename}"  # store relative path

            db.session.commit()
            
            # Update the session data to reflect changes immediately
            session['doctor_details'].update(request.form.to_dict())
            session['doctor_details']['image'] = doctor_to_update.image # Explicitly update image path in session
            session.modified = True

            flash('Your profile has been updated successfully!', 'success')
            return redirect(url_for('my_profile'))

        return render_template('edit_doctor_profile.html', doctor=doctor_to_update)

    @app.route('/update_appointment_status/<int:appointment_id>/<string:status>', methods=['POST'])
    def update_appointment_status(appointment_id, status):
        if "doctor_id" not in session:
            return redirect(url_for('doctor_login'))

        appointment = Appointment.query.get_or_404(appointment_id)
        # Ensure the appointment belongs to the logged-in doctor
        if appointment.doctor_id != session['doctor_id']:
            flash("You are not authorized to update this appointment.", "danger")
            return redirect(url_for('doctor_dashboard'))

        if status in ['Confirmed', 'Completed', 'Canceled']:
            appointment.status = status
            db.session.commit()
            flash(f"Appointment has been marked as {status}.", "success")
        else:
            flash("Invalid status update.", "danger")

        return redirect(url_for('doctor_dashboard'))

    @app.route('/doctor/manage_slots', methods=['GET', 'POST'])
    @doctor_verified_required
    def manage_slots():
        if "doctor_id" not in session:
            return redirect(url_for('doctor_login'))

        doctor = Doctor.query.get(session['doctor_id'])
        if not doctor:
            flash("Doctor not found.", "danger")
            return redirect(url_for('doctor_login'))

        if request.method == 'POST':
            # The form will submit all slots as a JSON string
            slots_data_str = request.form.get('slots_data')
            try:
                # Sort times for each date
                slots_data = json.loads(slots_data_str)
                for date in slots_data:
                    slots_data[date].sort()
            except (json.JSONDecodeError, TypeError):
                slots_data = {}
            
            doctor.available_slots = slots_data
            db.session.commit()

            session['doctor_details']['available_slots'] = doctor.available_slots
            session.modified = True

            flash("Your available slots have been updated successfully.", "success")
            return redirect(url_for('doctor_dashboard'))

        return render_template('manage_slots.html', doctor=session.get('doctor_details'))

    @app.route('/doctor/write_prescription/<int:appointment_id>', methods=['GET', 'POST'])
    @doctor_login_required
    @doctor_verified_required
    def write_prescription(appointment_id):
        appointment = Appointment.query.get_or_404(appointment_id)
        
        # Security check: ensure the appointment belongs to the logged-in doctor
        if appointment.doctor_id != session['doctor_id']:
            flash("You are not authorized to access this appointment.", "danger")
            return redirect(url_for('doctor_dashboard'))
    
        # A prescription can only be written for a confirmed or completed appointment
        if appointment.status not in ['Confirmed', 'Completed']:
            flash("Prescriptions can only be written for confirmed or completed appointments.", "warning")
            return redirect(url_for('doctor_dashboard'))
    
        # Check if a prescription already exists for this appointment
        prescription = appointment.prescription # Using the backref
    
        if request.method == 'POST':
            medication_details = request.form.get('medication_details') # This will be the JSON string
            notes = request.form.get('notes')
    
            # Basic validation: ensure we have some medication data.
            try:
                meds = json.loads(medication_details)
                if not isinstance(meds, list) or not meds:
                    flash("At least one medication is required.", "danger")
                    return render_template('write_prescription.html', appointment=appointment, prescription=prescription)
            except (json.JSONDecodeError, TypeError):
                flash("Invalid medication data format. Please try again.", "danger")
                return render_template('write_prescription.html', appointment=appointment, prescription=prescription)

            if prescription:
                # Update existing prescription
                prescription.medication_details = medication_details
                prescription.notes = notes
                flash("Prescription updated successfully.", "success")
            else:
                # Create new prescription
                new_prescription = Prescription(
                    appointment_id=appointment.id, 
                    doctor_id=appointment.doctor_id, 
                    patient_id=appointment.user_id, 
                    medication_details=medication_details, 
                    notes=notes
                )
                db.session.add(new_prescription)
                flash("Prescription created successfully.", "success")
            
            db.session.commit()
            return redirect(url_for('doctor_dashboard'))
    
        return render_template('write_prescription.html', appointment=appointment, prescription=prescription)

    @app.route('/doctor/send_email_verification')
    @doctor_login_required
    def send_doctor_email_verification():
        is_mail_configured = all([current_app.config.get('MAIL_SERVER'), current_app.config.get('MAIL_USERNAME'), current_app.config.get('MAIL_PASSWORD')])

        if not is_mail_configured:
            flash("The email service is not configured. Please contact support.", "danger")
            return redirect(url_for('my_profile'))

        if not check_gmail_app_password():
            return redirect(url_for('my_profile'))

        doctor = Doctor.query.get(session['doctor_id'])
        if not doctor.email_id:
            flash('Please add an email address to your profile first.', 'warning')
            return redirect(url_for('edit_doctor_profile'))

        if hasattr(doctor, 'email_verified') and doctor.email_verified:
            flash('Your email is already verified.', 'info')
            return redirect(url_for('my_profile'))

        # Generate and store OTP
        otp = str(random.randint(100000, 999999))
        session['doctor_email_verification_otp'] = otp
        session['doctor_email_to_verify'] = doctor.email_id

        # Send email with OTP
        msg = MailMessage('Verify Your Email for CareConnect',
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[doctor.email_id])
        msg.body = f'Your CareConnect Doctor account email verification OTP is: {otp}'
        try:
            mail.send(msg)
            flash(f'An OTP has been sent to {doctor.email_id}.', 'info')
        except smtplib.SMTPAuthenticationError as e:
            error_msg = Markup("Email sending failed due to an authentication error. If using Gmail, please use a 16-character <strong>App Password</strong>. <a href='https://myaccount.google.com/apppasswords' target='_blank' class='alert-link'>Generate one here</a>.")
            flash(error_msg, "danger")
            current_app.logger.error(f"SMTPAuthenticationError: {e}. Check MAIL_USERNAME and MAIL_PASSWORD.")
            if current_app.debug:
                flash(Markup(f"DEV MODE: Email sending failed. You can <a href='{url_for('dev_bypass_doctor_email_verification')}' class='alert-link'>click here to bypass verification</a>."), 'info')
            return redirect(url_for('my_profile'))

        return redirect(url_for('verify_doctor_email_otp'))

    @app.route('/doctor/verify_email_otp', methods=['GET', 'POST'])
    @doctor_login_required
    def verify_doctor_email_otp():
        if 'doctor_email_verification_otp' not in session:
            flash('Verification process has expired. Please try again.', 'warning')
            return redirect(url_for('my_profile'))

        if request.method == 'POST':
            submitted_otp = request.form.get('otp')
            if submitted_otp == session.get('doctor_email_verification_otp'):
                doctor = Doctor.query.get(session['doctor_id'])
                if doctor.email_id == session.get('doctor_email_to_verify'):
                    doctor.email_verified = True
                    db.session.commit()
                    if 'doctor_details' in session:
                        session['doctor_details']['email_verified'] = True
                        session.modified = True
                    flash('Your email has been successfully verified!', 'success')
                    session.pop('doctor_email_verification_otp', None)
                    session.pop('doctor_email_to_verify', None)
                    return redirect(url_for('my_profile'))
                else:
                    flash('Email address has changed. Please restart verification.', 'danger')
                    return redirect(url_for('my_profile'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        
        return render_template('doctor_verify_email.html')

    @app.route('/doctor/verify_phone_token', methods=['POST'])
    @doctor_login_required
    def verify_doctor_phone_token():
        """
        Verifies a Firebase Auth ID token sent from the client for a doctor.
        """
        id_token = request.json.get('token')
        if not id_token:
            return jsonify({'success': False, 'error': 'No token provided.'}), 400

        try:
            decoded_token = auth.verify_id_token(id_token)
            firebase_phone_number = decoded_token.get('phone_number')

            doctor = Doctor.query.get(session['doctor_id'])

            if doctor.mobile_no == firebase_phone_number:
                doctor.mobile_verified = True
                db.session.commit()
                # Update session to reflect the change immediately
                if 'doctor_details' in session:
                    session['doctor_details']['mobile_verified'] = True
                    session.modified = True
                flash('Your mobile number has been successfully verified!', 'success')
                return jsonify({'success': True})
            else:
                error_msg = f'Verified number ({firebase_phone_number}) does not match your profile number ({doctor.mobile_no}). Please update your profile and try again.'
                return jsonify({'success': False, 'error': error_msg}), 400

        except auth.InvalidIdTokenError:
            return jsonify({'success': False, 'error': 'The provided token is invalid.'}), 401
        except Exception as e:
            current_app.logger.error(f"Firebase token verification failed for doctor {session['doctor_id']}: {e}")
            return jsonify({'success': False, 'error': 'An internal server error occurred during verification.'}), 500

    @app.route('/dev/bypass_doctor_mobile_verification')
    @doctor_login_required
    def dev_bypass_doctor_mobile_verification():
        """
        A developer-only route to bypass doctor mobile verification.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        doctor = Doctor.query.get(session['doctor_id'])
        doctor.mobile_verified = True
        db.session.commit()
        if 'doctor_details' in session:
            session['doctor_details']['mobile_verified'] = True
            session.modified = True
        flash('DEV MODE: Mobile number verification bypassed.', 'success')
        return redirect(url_for('my_profile'))

    @app.route('/dev/bypass_doctor_email_verification')
    @doctor_login_required
    def dev_bypass_doctor_email_verification():
        """
        A developer-only route to bypass doctor email verification.
        """
        if not current_app.debug:
            return "This feature is only available in development mode.", 404
        
        doctor = Doctor.query.get(session['doctor_id'])
        doctor.email_verified = True
        db.session.commit()
        if 'doctor_details' in session:
            session['doctor_details']['email_verified'] = True
            session.modified = True
        flash('DEV MODE: Email verification bypassed.', 'success')
        return redirect(url_for('my_profile'))

    @app.route('/doctor/messages')
    @doctor_login_required
    @doctor_verified_required
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
    @doctor_verified_required
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