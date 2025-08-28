import os
import json
from flask import render_template, request, session, redirect, url_for, Blueprint
from services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist
from models import SearchHistory
from extension import db

def setup_routes(app):
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


    # main_routes = Blueprint('main_routes', __name__)
    @app.route('/find_doctor', methods=['GET', 'POST'])
    def find_doctor():
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        file_path = os.path.join(project_root, "data", "doctors.json")
        file_path = os.path.normpath(file_path)
        with open(file_path, 'r') as f:
            doctors_data = json.load(f)
        location_filter = request.form.get('location', '').lower()
        specialization_filter = request.form.get('specialization', '').lower()

        results = []
        for entry in doctors_data:
            location_match = location_filter in entry['hospital']['address'].lower()
            specialization_match = specialization_filter in entry['specialization'].lower()
            if request.method == 'POST' and not (location_match and specialization_match):
                continue  # skip non-matching entries
            results.append({
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
        return render_template('doctor_results.html', doctors=results)

    @app.route("/about")
    def about():
        return render_template("about.html")
    
    @app.route("/contactus")
    def contactus():
        return render_template("contactus.html")