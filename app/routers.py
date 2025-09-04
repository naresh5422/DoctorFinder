import os
import json
from flask import render_template, request, session, redirect, url_for, flash
from services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist
from models import SearchHistory, User
from extension import db, login_required


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
file_path = os.path.join(project_root, "data", "doctors.json")
file_path = os.path.normpath(file_path)


def setup_routes(app):
    @app.context_processor
    def inject_user():
        user = None
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
        return dict(user=user)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            session["next_url"] = request.args.get("next") or request.referrer
            return render_template("login.html")
        # POST: handle login
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user_id"] = user.id
            user.login_count += 1
            user.status = "login"
            db.session.commit()
            next_url = session.pop("next_url", None)
            if next_url and "/signup" in next_url:
                next_url = url_for("index")
            return redirect(next_url or url_for("index"))  # Adjust if using blueprint
        else:
            flash("Invalid username or password", "danger")
        return render_template("login.html")
    
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            name = request.form.get("name")
            mobile = request.form.get("mobile")
            email = request.form.get("email")
            location = request.form.get("location")
            # Check if user already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash("Username already taken. Please choose another one.", "warning")
                return render_template("signup.html")
            # Create new user
            user = User(
                username=username,
                password=password,   # ⚠️ you should hash password later using werkzeug.security
                name=name,
                mobile=mobile,
                email=email,
                location=location
            )
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("signup.html")


    @app.route("/logout")
    def logout():
        user_id = session.get("user_id")
        if user_id:
            user = User.query.get(user_id)
            if user:
                user.status = "logout"
                db.session.commit()
        session.pop("user_id", None)
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))


    @app.route("/")
    def index():
        return render_template("index.html")
    
    @app.route("/repeat_search", defaults={"search_id": None})
    @app.route("/repeat_search/<int:search_id>", methods = ["GET","POST"])
    @login_required
    def repeat_search(search_id):
        if "user_id" not in session:
            return redirect(url_for("login"))
        search = SearchHistory.query.get(search_id)
        if not search or search.user_id != session["user_id"]:
            return "Unauthorized or invalid search"
        nearby_locations = get_nearby_locations(search.location)
        specialist = map_disease_to_specialist(search.disease)
        results = find_doctors(nearby_locations, specialist)
        recent_searches = SearchHistory.query.filter_by(user_id=session["user_id"]).order_by(SearchHistory.timestamp.desc()).limit(5).all()
        return render_template("index.html", results=results, recent_searches=recent_searches)

    @app.route('/find_doctor', methods=['GET', 'POST'])
    @login_required
    def find_doctor():
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        results = []
        recent_searchs = []
        if request.method == "POST":
            location = request.form.get("location", "")
            disease = request.form.get("disease")
            # 🔹 Map layman term OR specialist to professional mapping
            specialist_mapping = map_disease_to_specialist(disease)
            specialist = specialist_mapping.split(" - ")[1]
            # Save search to database
            search = SearchHistory(user_id=session["user_id"],
                                   location=location,
                                   disease=disease)
            db.session.add(search)
            db.session.commit()
            ## Doctor search logic
            nearby_locations = get_nearby_locations(location.strip().lower())
            # results = find_doctors(nearby_locations, specialist)
            results = [doc for doc in doctors_data
                       if doc['location'].lower() in nearby_locations
                       and doc['specialization'] == specialist]
            recent_searchs = (
                SearchHistory.query.filter_by(user_id=session["user_id"])
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
    
    # Doctor Services
    @app.route('/doctor_profile', methods = ['GET','POST'])
    @login_required
    def doctor_profile():
        doctors = []   # ✅ Always initialize
        doctor_name = ""  # ✅ Default empty (to avoid undefined in template)
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        if request.method == 'POST':
            if "review_text" in request.form and "doctor_id" in request.form:
                doctor_id_str = request.form.get("doctor_id", "").strip()
                doctor_id = int(doctor_id_str) if doctor_id_str.isdigit() else None
                review_text = request.form["review_text"].strip()
                for doc in doctors_data:
                    if doc.get("id") == doctor_id:
                        if "reviews" not in doc:
                            doc["reviews"] = []
                        doc["reviews"].append(review_text)
                # Save updated JSON
                with open(file_path, 'w') as f:
                    json.dump(doctors_data, f, indent=4)
                # Redirect back to doctor search result
                return redirect(url_for("doctor_profile", doctor_name=request.args.get("doctor_name", "")))
            doctor_name = request.form.get('doctor_name', '').strip().lower()
            doctors = [doc for doc in doctors_data if doctor_name in doc['doctor_name'].lower()]
        return render_template('doctor_profile.html', doctors=doctors, doctor_name=doctor_name)


    # Hospital Services
    @app.route('/hospital_finding')
    @login_required
    def hospital_finder():
        return render_template('hospital_finder.html')
    
    @app.route('/user_profile')
    @login_required
    def user_profile():
        return render_template('user_profile.html')

    @app.route('/hospital_doctor')
    @login_required
    def hospital_doctor():
        return render_template('hospital_doctor.html')

    @app.route('/hospital_reviews')
    @login_required
    def hospital_reviews():
        return render_template('hospital_reviews.html')


    # Doctor Registration
    # @app.route("/doctor_register", methods=["GET", "POST"])
    # def doctor_register():
    #     if request.method == "POST":
    #         doctor_data = {
    #             "doctor_name": request.form.get("name"),
    #             "username": request.form.get("username"),
    #             "specialization": request.form.get("specialization"),
    #             "experience": int(request.form.get("experience", 0)),
    #             "password": request.form.get("password"),  # ⚠️ should be hashed ideally
    #             "mobileno": request.form.get("mobileno"),
    #             "emailid": request.form.get("emailid"),
    #             "location": request.form.get("location"),
    #             "hospital": request.form.get("hospital")}
    #         if not all([doctor_data["doctor_name"], 
    #                     doctor_data["username"],
    #                     doctor_data['specialization'],
    #                     doctor_data['experience'], 
    #                     doctor_data["password"], 
    #                     doctor_data["mobileno"],
    #                     doctor_data['emailid'], 
    #                     doctor_data["location"],
    #                     doctor_data['hospital']]):
    #             flash("Please fill all required fields", "danger")
    #             return redirect(url_for("doctor_registration"))
    #         current_dir = os.path.dirname(os.path.abspath(__file__))
    #         project_root = os.path.dirname(current_dir)
    #         file_path = os.path.join(project_root, "data", "doctors.json")
    #         file_path = os.path.normpath(file_path)
    #         if os.path.exists(file_path):
    #             with open(file_path, "r") as f:
    #                 try:
    #                     doctors = json.load(f)
    #                 except json.JSONDecodeError:
    #                     doctors = []
    #         else:
    #             doctors = []
    #         if any(doc["username"].lower() == doctor_data["username"].lower() for doc in doctors):
    #             flash("Username already exists. Please choose another one.", "danger")
    #             return redirect(url_for("doctor_registration"))
    #         doctors.append(doctor_data)
    #         with open(file_path, "w") as f:
    #             json.dump(doctors, f, indent=4, ensure_ascii=False)
    #         flash("Signup successful! Please login.", "success")
    #         return redirect(url_for("doctor_login"))
    #     return render_template("doctor_registration.html")

    @app.route("/doctor_register", methods=["GET", "POST"])
    def doctor_register():
        if request.method == "POST":
            # Collect doctor data from form
            # Path to doctors.json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            file_path = os.path.join(project_root, "data", "doctors.json")
            file_path = os.path.normpath(file_path)

            # Load existing doctors
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    try:
                        doctors = json.load(f)
                    except json.JSONDecodeError:
                        doctors = []
            else:
                doctors = []
            ids = [doc.get("id") for doc in doctors if isinstance(doc.get("id"), int)]
            new_id = (max(ids) if ids else 100) + 1
            doctor_data = {
                "id": new_id,
                "username": request.form.get("username"),
                "password": request.form.get("password"),  # ⚠️ hash in production
                "doctor_name": request.form.get("name"),
                "specialization": request.form.get("specialization"),
                "MobileNo": request.form.get("mobile"),
                "EmailId": request.form.get("email"),
                "location": request.form.get("location"),
                "experience": int(request.form.get("experience", 0)),
                "rating": float(request.form.get("rating", 0.0)),  # optional
                "reviews": [],  # default empty list
                "hospital": {
                    "name": request.form.get("hospital_name"),
                    "address": request.form.get("hospital_address"),
                    "contact": request.form.get("hospital_contact")
                }
            }

            # Validate required fields
            if not all([doctor_data["username"], doctor_data["password"], doctor_data["doctor_name"],
                    doctor_data["specialization"], doctor_data["MobileNo"], doctor_data["EmailId"],
                    doctor_data["location"], doctor_data["hospital"]["name"]]):
                flash("Please fill all required fields", "danger")
                return redirect(url_for("doctor_register"))

            

            # Check for duplicate username
            if any(doc["username"].lower() == doctor_data["username"].lower() for doc in doctors):
                flash("Username already exists. Please choose another one.", "danger")
                return redirect(url_for("doctor_register"))

            # Generate new ID
            # new_id = max([doc.get("id") for doc in doctors], default=100) + 1
            # doctor_data["id"] = new_id


            # Append new doctor
            doctors.append(doctor_data)

            # Save back to JSON
            with open(file_path, "w") as f:
                json.dump(doctors, f, indent=4, ensure_ascii=False)

            flash("Doctor registered successfully!", "success")
            return redirect(url_for("doctor_login"))

        return render_template("doctor_registration.html")

    # Doctor Login
    @app.route("/doctor_login", methods=["GET", "POST"])
    def doctor_login():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"].strip()
            with open(file_path, 'r') as f:
                doctors_data = json.load(f)
            doctor = next((doc for doc in doctors_data if doc["username"] == username and doc["password"] == password), None)
            if doctor:
                session["doctor_id"] = doctor["id"]
                session["doctor_name"] = doctor["doctor_name"]
                return redirect(url_for("doctor_dashboard"))
            else:
                return "Invalid username or password!"
        return render_template("doctor_login.html")


    # Doctor Dashboard (after login)
    @app.route("/doctor_dashboard")
    def doctor_dashboard():
        if "doctor_id" not in session:
            return redirect(url_for("doctor_login"))
        doctor_id = session["doctor_id"]
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        doctor = next((doc for doc in doctors_data if doc.get("id") == doctor_id), None)
        return render_template("doctor_dashboard.html", doctor=doctor)


    # Doctor Logout
    @app.route("/doctor_logout")
    def doctor_logout():
        session.clear()
        return redirect(url_for("doctor_login"))