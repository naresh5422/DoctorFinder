from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

# config.py
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://root:Sulochana%40522@127.0.0.1:3306/DoctorFinder_DB"
SQLALCHEMY_TRACK_MODIFICATIONS = False