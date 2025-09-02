import os
import json
from flask import render_template, request, session, redirect, url_for, Blueprint
from services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist
from models import SearchHistory, User
from extension import db

def setup_routes(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            session["next_url"] = request.referrer
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
            return redirect(next_url or url_for("main_routes.index"))  # Adjust if using blueprint
        else:
            return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            user = User(
                username=request.form["username"],
                password=request.form["password"],
                name=request.form["name"],
                mobile=request.form["mobile"],
                email=request.form.get("email"),
                location=request.form["location"]
            )
            db.session.add(user)
            db.session.commit()
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
        return redirect(url_for("login"))


    @app.route("/", methods=["GET", "POST"])
    def index():
        if "user_id" not in session:
            return render_template("login.html")
        results = []
        recent_searchs = []
        if request.method == "POST":
            location = request.form.get("location")
            disease = request.form.get("disease")
            # Save search to database
            search = SearchHistory(user_id=session["user_id"],location=location,disease=disease)
            db.session.add(search)
            db.session.commit()
            ## Doctor search logic
            nearby_locations = get_nearby_locations(location)
            specialist = map_disease_to_specialist(disease)
            results = find_doctors(nearby_locations, specialist)
        recent_searchs = SearchHistory.query.filter_by(user_id=session["user_id"]).order_by(SearchHistory.id.desc()).limit(5).all()
        return render_template("index.html", results=results, recent_searches=recent_searchs)
    
    @app.route("/repeat_search", defaults={"search_id": None})
    @app.route("/repeat_search/<int:search_id>", methods = ["GET","POST"])
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
    def find_doctor():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        file_path = os.path.join(project_root, "data", "doctors.json")
        file_path = os.path.normpath(file_path)
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        filtered_doctors = []
        if request.method == 'POST':
            location_input = request.form.get('location', '').strip().lower()
            disease_input = request.form.get('disease', '').strip().lower()
            for entry in doctors_data:
                # location_match = location_input in entry['hospital']['address'].lower()
                location_match = location_input in entry['location'].lower()
                specialization_match = disease_input in entry['specialization'].lower()
                if location_match and specialization_match:
                    filtered_doctors.append({
                    "doctor_name": entry["doctor_name"],
                    "specialization": entry["specialization"],
                    "experience": entry["experience"],
                    "rating": entry["rating"],
                    "reviews": entry["reviews"],
                    "map_link": f"https://www.google.com/maps/search/{entry['hospital']['address'].replace(' ', '+')}",
                    "hospital_name": entry["hospital"]["name"],
                    "hospital_address": entry["hospital"]["address"],
                    "hospital_contact": entry["hospital"]["contact"]
                })
        return render_template('doctor_finding.html', doctors=filtered_doctors)
    
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
    def doctor_profile():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        file_path = os.path.join(project_root, "data", "doctors.json")
        file_path = os.path.normpath(file_path)
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        # if doctor_name:
        #     filtered_doctors = [doc for doc in doctors_data if doctor_name.lower() in doc['doctor_name'].lower()]
        # else:
        #     filtered_doctors = []
        if request.method == 'POST':
            doctor_name = request.form.get('doctor_name', '').strip().lower()
            doctors = [doc for doc in doctors_data if doctor_name in doc['doctor_name'].lower()]
        # return render_template("doctor_profile.html", doctors=doctors)
        return render_template('doctor_profile.html', doctors=doctors, doctor_name=doctor_name)


    @app.route('/doctor_reviews')
    def doctor_reviews():
        return render_template('doctor_reviews.html')

    # Hospital Services
    @app.route('/hospital_finding')
    def hospital_finder():
        return render_template('hospital_finder.html')

    @app.route('/hospital_doctor')
    def hospital_doctor():
        return render_template('hospital_doctor.html')

    @app.route('/hospital_reviews')
    def hospital_reviews():
        return render_template('hospital_reviews.html')
