# CareConnect - Intelligent Doctor Finder

CareConnect is a modern, full-stack web application designed to bridge the gap between patients and healthcare professionals. It provides an intelligent, AI-powered search engine to help users find the right doctor based on their symptoms and location, book appointments, and manage their healthcare journey seamlessly.

![Homepage Screenshot](https://via.placeholder.com/800x400.png?text=CareConnect+Homepage)

## ✨ Key Features

-   **AI-Powered Search**:
    -   **Semantic Search**: Understands user queries for symptoms (e.g., "high bp" maps to "Cardiologist").
    -   **Natural Language Processing (NLP)**: Extracts locations automatically from search queries (e.g., "skin doctor in Gachibowli").
    -   **Multi-Location Search**: Search for doctors across multiple cities or areas in a single query.
-   **Dual User Portals**: Separate, secure login and dashboard areas for both **Patients** and **Doctors**.
-   **Comprehensive Doctor Profiles**: View doctor specializations, experience, ratings, patient reviews, and hospital affiliations.
-   **Appointment Booking System**:
    -   View real-time doctor availability.
    -   Book, manage, and view upcoming and past appointments.
-   **Patient Dashboard**: A personalized space to view search history, manage appointments, and access conversations.
-   **Real-time Messaging**: Secure, one-on-one chat between patients and doctors.
-   **Hospital Finder**: Search for hospitals by location and view their services.
-   **User Profile Management**: Patients can update their profile, upload a photo, and verify their email and mobile number.
-   **Verification System**: Email verification via Flask-Mail and mobile number verification via Twilio OTP.
-   **Dynamic Autocomplete**: Fast and relevant search suggestions for symptoms, specialties, and locations.

## 🛠️ Tech Stack

-   **Backend**: Python, Flask, SQLAlchemy
-   **Database**: PostgreSQL
-   **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
-   **AI & Machine Learning**:
    -   `sentence-transformers` for semantic similarity.
    -   `spacy` for Named Entity Recognition (NER).
-   **External APIs & Services**:
    -   **Twilio**: For sending SMS OTPs for mobile verification.
    -   **Flask-Mail**: For sending email (e.g., for email verification).

## 📂 Project Structure

```
DoctorFinder/
├── app/
│   ├── static/         # CSS, JS, Images
│   ├── templates/      # HTML templates
│   ├── __init__.py     # Flask app factory
│   ├── config.py       # Configuration settings
│   ├── extension.py    # Flask extensions (db, mail)
│   ├── models.py       # SQLAlchemy database models
│   ├── routers.py      # Application routes and view logic
│   └── services/
│       └── doctor_service.py # Business logic, AI search, data processing
├── data/
│   └── data_create.py  # Script to generate dummy data
├── migrations/         # Alembic migration files
├── .env                # Environment variables (local)
├── .flaskenv           # Flask environment settings
├── requirements.txt    # Python dependencies
└── run.py              # Application entry point
```

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

-   Python 3.8+
-   MySQL
-   Git

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/DoctorFinder.git
    cd DoctorFinder
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download the spaCy NLP model:**
    This is required for Natural Language Processing features.
    ```bash
    python -m spacy download en_core_web_sm
    ```

5.  **Set up the Database:**
    -   Make sure you have PostgreSQL installed and running.
    -   Create a new database for the project.
    ```sql
    CREATE DATABASE doctor_db;
    ```

6.  **Configure Environment Variables:**
    -   Create a `.env` file in the root directory by copying the example below.
    -   Update the values with your own configuration (database URL, email credentials, Twilio keys, etc.).

    **.env file:**
    ```env
    # Flask Configuration
    SECRET_KEY='a_very_secret_and_long_random_string'
    FLASK_APP=run.py
    FLASK_ENV=development

    # Database URL (PostgreSQL)
    DATABASE_URL="postgresql://user:password@localhost:5432/doctor_db"

    # Email Configuration (e.g., for Gmail)
    MAIL_SERVER=smtp.gmail.com
    MAIL_PORT=587
    MAIL_USE_TLS=True
    MAIL_USERNAME='your-email@gmail.com'
    MAIL_PASSWORD='your-app-password' # Use an App Password for Gmail

    # Twilio Configuration (for SMS OTP)
    TWILIO_ACCOUNT_SID='ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    TWILIO_AUTH_TOKEN='your_auth_token'
    TWILIO_PHONE_NUMBER='+15017122661' # Your Twilio phone number
    ```

7.  **Initialize the Database:**
    -   Run the Flask-Migrate commands to create the database tables.
    ```bash
    flask db init  # Only if the 'migrations' folder doesn't exist
    flask db migrate -m "Initial migration"
    flask db upgrade
    ```

8.  **Run the application:**
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`.

## 💡 Usage

-   **Patient**: Navigate to the homepage, sign up for an account, and log in. Use the search bar to find doctors by symptom or specialty. You can also search for hospitals. Book appointments from a doctor's profile.
-   **Doctor**: Log in to the doctor portal to view your appointments, manage your schedule, and chat with patients.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License.
