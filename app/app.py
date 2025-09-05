import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configure Upload Folder
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

# Make sure the folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Optional: restrict file size (2 MB here)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
