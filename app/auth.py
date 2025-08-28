from flask import render_template, request, redirect, session, url_for
from extension import db
from models import User

def setup_auth(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            # Save the previous page so we can redirect after login
            session["next_url"] = request.referrer
            return render_template("login.html")

        # POST method: handle login submission
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()

        if user:
            user.login_count += 1
            user.status = "login"
            db.session.commit()
            session["user_id"] = user.id

            # Redirect to previous page or homepage
            next_url = session.pop("next_url", None)
            return redirect(next_url or url_for("index"))
        else:
            return "Invalid credentials"

    # def login():
    #     if request.method == "POST":
    #         username = request.form["username"]
    #         password = request.form["password"]
    #         user = User.query.filter_by(username=username, password=password).first()
    #         if user:
    #             user.login_count += 1
    #             user.status = 'login'
    #             db.session.commit()
    #             session["user_id"] = user.id
    #             return redirect(url_for("index"))
    #         else:
    #             return "Invalid credentials"
    #     return render_template("login.html")


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