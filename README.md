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
-   **Database**: MySQL (for local development), PostgreSQL (for production deployment)
-   **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, JQuery
-   **AI & Machine Learning**:
    -   `sentence-transformers` for semantic similarity.
    -   `spacy` for Named Entity Recognition (NER).
-   **External APIs & Services**:
    -   **Firebase Authentication**: For sending SMS OTPs for mobile verification (free tier).
    -   **Flask-Mail**: For sending email verification via any SMTP provider (e.g., Gmail, Brevo).

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
    -   Make sure you have MySQL installed and running.
    -   Create a new database (schema) for the project.
    ```sql
    CREATE DATABASE DoctorFinder_DB;
    ```

6.  **Configure Environment Variables:**
    -   Create a `.env` file in the root directory by copying the example below.
    -   Update the values with your own configuration (database URL, email credentials, Twilio keys, etc.).

    **.env file:**
    ```dotenv
    # Flask Configuration
    SECRET_KEY='a_very_secret_and_long_random_string'
    FLASK_APP=run.py
    FLASK_ENV=development

    # Database URL (MySQL)
    DATABASE_URL="mysql+mysqlconnector://root:Sulochana%40522@localhost:3306/DoctorFinder_DB"

    # --- Email Configuration ---
    # Option 1: Brevo (Recommended for easy setup)
    # Get credentials from your Brevo account -> SMTP & API -> SMTP tab
    MAIL_SERVER="smtp-relay.brevo.com"
    MAIL_PORT=587
    MAIL_USE_TLS=True
    MAIL_USERNAME="your-brevo-login-email@example.com"
    MAIL_PASSWORD="Your-Brevo-SMTP-Key"

    # Option 2: Gmail (Requires App Password)
    # MAIL_SERVER="smtp.gmail.com"
    # MAIL_USERNAME="your-email@gmail.com" 
    # IMPORTANT: For Gmail, you MUST use a 16-character "App Password".
    # 1. Enable 2-Step Verification on your Google Account.
    # 2. Go to https://myaccount.google.com/apppasswords to generate one.
    # MAIL_PASSWORD="your-generated-app-password"

    # --- Firebase Configuration ---
    # 1. For Backend (Admin SDK) - Set this to the path of your service account JSON file.
    GOOGLE_APPLICATION_CREDENTIALS="D:/path/to/your/firebase-service-account.json"

    # 2. For Frontend (Web SDK) - Get these from your Firebase project settings.
    FIREBASE_API_KEY="AIzaSy..."
    FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
    FIREBASE_PROJECT_ID="your-project"
    FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
    FIREBASE_MESSAGING_SENDER_ID="123456789"
    FIREBASE_APP_ID="1:123456789:web:abcdef123456"

    # Twilio Configuration (for Doctor password reset via SMS)
    TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWILIO_AUTH_TOKEN="your_auth_token"
    TWILIO_PHONE_NUMBER="+15017122661" # Your Twilio phone number
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

## ☁️ Deployment

This application is ready to be deployed on cloud platforms like Render. Here are the steps to deploy on Render's free tier.

### 1. Prepare for Deployment

Make sure your project is pushed to a GitHub repository.

### 2. Set Up on Render

> **Database Note**: These instructions use Render's free PostgreSQL database for deployment, which is different from the local MySQL setup. The application is configured to handle this switch automatically via the `DATABASE_URL` environment variable.

1.  **Create a PostgreSQL Database**:
    -   In the Render dashboard, go to **New > PostgreSQL**.
    -   Choose a name and select the **Free** plan.
    -   After creation, go to the database's "Info" page and copy the **Internal Database URL**. You will use this for the `DATABASE_URL` environment variable.

2.  **Create a Web Service**:
    -   Go to **New > Web Service** and connect your GitHub repository.
    -   Render will detect it's a Python app. Configure the following settings:
        -   **Runtime**: `Python 3`
        -   **Build Command**: `pip install -r requirements.txt && python -m spacy download en_core_web_sm && flask db upgrade`
        -   **Start Command**: `gunicorn run:app`

3.  **Add Environment Variables**:
    -   Under the "Environment" tab for your web service, add all the variables from your local `.env` file.
    -   `DATABASE_URL`: Paste the Internal Database URL from your Render PostgreSQL instance.
    -   `FLASK_ENV`: Set this to `production`.
    -   `SECRET_KEY`: Generate a new, strong random string for production. You can use `python -c "import secrets; print(secrets.token_hex(32))"` to generate one.
    -   `PYTHON_VERSION`: Set this to your Python version (e.g., `3.11.0`).
    -   **Handling `GOOGLE_APPLICATION_CREDENTIALS`**:
        -   This is a special case. Instead of a file path, you need to store the content of your `firebase-service-account.json` file.
        -   In the Render dashboard, create the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.
        -   Open your local `.json` file, copy its **entire content**, and paste it into the value field in Render. Render supports multi-line variables.

### 3. Deploy

-   Click **Create Web Service**. Render will build your application, run the database migrations, and start the service.
-   Your application will be live at the `.onrender.com` URL provided in your dashboard.

> **Note on Free Tier**: Render's free web services will "spin down" after a period of inactivity and may take 30-60 seconds to start up on the first request. This is normal for free hosting plans.

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
