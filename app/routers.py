from flask import render_template, request
from services.doctor_service import find_doctors, get_nearby_locations, map_disease_to_specialist

def setup_routes(app):
    @app.route("/", methods=["GET", "POST"])
    def index():
        results = []
        if request.method == "POST":
            location = request.form.get("location")
            disease = request.form.get("disease")

            nearby_locations = get_nearby_locations(location)
            specialist = map_disease_to_specialist(disease)
            results = find_doctors(nearby_locations, specialist)

        return render_template("index.html", results=results)
