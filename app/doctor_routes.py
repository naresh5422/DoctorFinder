import os
import json
from flask import render_template, request, session, redirect, url_for, flash, current_app
from datetime import date
from app.models import Doctor, Review, Appointment
from app.extension import db
from werkzeug.utils import secure_filename

def setup_doctor_routes(app):
    # Doctor Services
    @app.route('/doctor')
    def doctor_home():
        if 'doctor_id' in session:
            return redirect(url_for('doctor_dashboard'))
        return redirect(url_for('doctor_login'))

    @app.context_processor
    def inject_doctor():
        if 'doctor_id' in session:
            return dict(doctor_details=session.get('doctor_details'))
        return dict(doctor_details=None)


    @app.route('/doctor_profile', methods = ['GET','POST'])
    def doctor_profile():
        doctors = []
        doctor_name_query = ""

        if request.method == 'POST':
            if "review_text" in request.form and "doctor_id" in request.form:
                doctor_id_str = request.form.get("doctor_id", "").strip()
                doctor_id = int(doctor_id_str) if doctor_id_str.isdigit() else None
                review_text = request.form["review_text"].strip()
                if doctor_id and review_text and 'patient_id' in session:
                    new_review = Review(text=review_text, doctor_id=doctor_id, patient_id=session['patient_id'])
                    db.session.add(new_review)
                    db.session.commit()
                    flash("Your review has been submitted.", "success")
                return redirect(url_for("doctor_profile", doctor_name=request.args.get("doctor_name_query", "")))
            
            doctor_name_query = request.form.get('doctor_name', '').strip()
            if doctor_name_query:
                # Search doctors in the database
                doctors = Doctor.query.filter(Doctor.doctor_name.ilike(f'%{doctor_name_query}%')).all()
        
        # For GET requests with a query parameter
        elif 'doctor_name' in request.args:
            doctor_name_query = request.args.get('doctor_name', '')
            doctors = Doctor.query.filter(Doctor.doctor_name.ilike(f'%{doctor_name_query}%')).all()
            
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
                available_slots={"slots": []}
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
        # Placeholder for password reset logic
        return render_template("doctor_forgot_password.html")

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
                               booked_slots=booked_slots)

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