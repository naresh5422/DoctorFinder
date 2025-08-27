from flask import render_template, request, session
from services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist
from models import SearchHistory
from extension import db
def setup_routes(app):
    @app.route("/", methods=["GET", "POST"])
    def index():
        if "user_id" not in session:
            return render_template("login.html")

        results = []
        if request.method == "POST":
            location = request.form.get("location")
            disease = request.form.get("disease")
            # Save search to database
            search = SearchHistory(
                user_id=session["user_id"],
                location=location,
                disease=disease)
            db.session.add(search)
            db.session.commit()

            nearby_locations = get_nearby_locations(location)
            specialist = map_disease_to_specialist(disease)
            results = find_doctors(nearby_locations, specialist)

        return render_template("index.html", results=results)

