from extension import db
from datetime import datetime

class Doctor:
    def __init__(self, name, specialization, location):
        self.name = name
        self.specialization = specialization
        self.location = location


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))  # Optional
    location = db.Column(db.String(120), nullable=False)
    login_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(10), default="logout")
    image = db.Column(db.String(200), nullable=True)  # Path to profile image
    bio = db.Column(db.Text, nullable=True)  # Extra details

    def __repr__(self):
        return f"<User {self.username}>"
    
class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    disease = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, default = datetime.utcnow)

    def __repr__(self):
        return f"<User {self.user_id}>"

