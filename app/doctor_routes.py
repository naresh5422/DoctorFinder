import os
import json
import random
from flask import render_template, request, session, redirect, url_for, flash, current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_mail import Message
from twilio.rest import Client
from datetime import date, datetime 
from app.models import Doctor, Review, Appointment, Message
from app.extension import db, mail
from werkzeug.utils import secure_filename

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

                if doctor_id and review_text and 'patient_id' in session:
                    new_review = Review(text=review_text, rating=rating, doctor_id=doctor_id, patient_id=session['patient_id'])
                    db.session.add(new_review)

                    # Recalculate doctor's average rating
                    doctor = Doctor.query.get(doctor_id)
                    if doctor:
                        # Fetch all ratings for the doctor
                        all_reviews = Review.query.filter_by(doctor_id=doctor_id).all()
                        total_ratings = sum(r.rating for r in all_reviews)
                        average_rating = total_ratings / len(all_reviews)
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
                ).filter(Appointment.status.in_(['Confirmed', 'Completed'])).first()
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
        doctor = session.get('doctor_details')
        if not doctor: # This part remains as session holds the details
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
                available_slots='{}'
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
                    "reviews": doctor.review_texts, # Fetch review texts
                    "available_slots": doctor.available_slots,
                    "image": doctor.image
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
                    # Send a real email
                    reset_url = url_for('doctor_reset_with_token', token=token, _external=True)
                    msg = Message('Password Reset Request',
                                  sender=app.config['MAIL_USERNAME'],
                                  recipients=[doctor.email_id])
                    msg.body = f'''To reset your password, visit the following link:
{reset_url}
If you did not make this request then simply ignore this email and no changes will be made.'''
                    mail.send(msg)
                    flash(f"A password reset link has been sent to {doctor.email_id}.", "info")
                else:
                    # Generate a random 6-digit OTP
                    otp = str(random.randint(100000, 999999))
                    session['reset_otp'] = otp
                    session['reset_doctor_id'] = doctor.id

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
        doctor = session.get('doctor_details')

        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect(url_for("doctor_login"))
        
        # Appointments are still fetched from the database
        # We query appointments directly using the doctor_id from the session
        all_appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()

        pending_appointments = [a for a in all_appointments if a.status == 'Pending']
        confirmed_appointments = [a for a in all_appointments if a.status == 'Confirmed']
        completed_appointments = [a for a in all_appointments if a.status == 'Completed']

        # Create a set of booked "date time" strings for easy lookup in the template
        booked_slots = {
            f"{appt.appointment_date.strftime('%Y-%m-%d')}_{appt.appointment_date.strftime('%H:%M')}"
            for appt in all_appointments if appt.status in ['Pending', 'Confirmed']
        }

        return render_template("doctor_dashboard.html", doctor=doctor,
                               pending_appointments=pending_appointments,
                               confirmed_appointments=confirmed_appointments,
                               completed_appointments=completed_appointments,
                               today_date=date.today().isoformat(), 
                               booked_slots=booked_slots,
                               datetime=datetime)

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

        # Use doctor details from session, which come from the JSON file
        doctor_details = session.get('doctor_details')
        if not doctor_details:
            flash("Could not find your profile details. Please log in again.", "danger")
            return redirect(url_for("doctor_login"))

        doctor_to_update = Doctor.query.get(session['doctor_id'])
        if not doctor_to_update:
            flash("Could not find your profile in the database.", "danger")
            return redirect(url_for('doctor_login'))

        if request.method == 'POST':
            # Update the Doctor object with form data
            doctor_to_update.doctor_name = request.form.get('doctor_name')
            doctor_to_update.specialization = request.form.get('specialization')
            doctor_to_update.mobile_no = request.form.get('mobile_no')
            doctor_to_update.email_id = request.form.get('email_id')
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

        return render_template('edit_doctor_profile.html', doctor=doctor_details)

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

    # --- TEMPORARY DEBUGGING ROUTE ---
    # This route is for debugging the password issue.
    # Access it via /reset_doctor_password?username=THE_USERNAME&password=NEW_PASSWORD
    # REMOVE THIS ROUTE IN PRODUCTION
    @app.route('/reset_doctor_password')
    def reset_doctor_password():
        username = request.args.get('username')
        new_password = request.args.get('password')

        if not username or not new_password:
            return "Please provide 'username' and 'password' as query parameters.", 400

        doctor = Doctor.query.filter_by(username=username).first()
        if not doctor:
            return f"Doctor with username '{username}' not found.", 404

        doctor.set_password(new_password)
        db.session.commit()
        return f"Password for doctor '{username}' has been reset successfully. You can now log in with the new password."