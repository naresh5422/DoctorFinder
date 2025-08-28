from flask import render_template, request, session, redirect, url_for
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
