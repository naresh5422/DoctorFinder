# DATA_PATH = "data/doctors.json"
import os

class Settings:
    PROJECT_NAME: str = "CareConnect"
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root:Sulochana%40522@localhost:3306/DoctorFinder_DB")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-that-is-not-secure-and-should-be-changed")

    # Email Configuration
    MAIL_SERVER: str = os.getenv("MAIL_SERVER")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS: bool = os.getenv("MAIL_USE_TLS", "true").lower() in ('true', '1', 't')
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD")
    
    # Twilio (SMS) Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER")

    # Firebase Web SDK Configuration (for frontend)
    FIREBASE_API_KEY: str = os.getenv("FIREBASE_API_KEY")
    FIREBASE_AUTH_DOMAIN: str = os.getenv("FIREBASE_AUTH_DOMAIN")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET")
    FIREBASE_MESSAGING_SENDER_ID: str = os.getenv("FIREBASE_MESSAGING_SENDER_ID")
    FIREBASE_APP_ID: str = os.getenv("FIREBASE_APP_ID")

    # File Uploads
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "app/static/uploads")
    MAX_CONTENT_LENGTH: int = 2 * 1024 * 1024  # 2 MB

settings = Settings()