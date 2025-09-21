import os
import logging
from app.main import create_app
from dotenv import load_dotenv

# Configure logging for clearer startup messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Load environment variables from .env file at the very beginning
# This returns True if the .env file was found and loaded.
env_loaded = load_dotenv()

# --- BEGIN: Developer Experience Improvement ---
# Provide clear feedback about the .env file status. This helps clarify
# that the application handles loading the .env file itself, independent of
# terminal settings like 'python.terminal.useEnvFile'.
if env_loaded:
    logging.info("✅ '.env' file found and loaded by the application.")
    # Add a specific check for Gmail App Passwords to improve developer experience.
    if os.getenv('MAIL_SERVER') == 'smtp.gmail.com':
        mail_password = os.getenv('MAIL_PASSWORD', '')
        # Google App Passwords are 16 characters long and don't contain spaces. This is a good heuristic.
        if ' ' in mail_password or (mail_password and len(mail_password) != 16):
             logging.warning("   -> ⚠️  Using Gmail SMTP. Ensure 'MAIL_PASSWORD' is a 16-character App Password, not your regular Google password. Generate one at https://myaccount.google.com/apppasswords")
else:
    logging.warning("⚠️ '.env' file not found. Application might not be configured. See README.md for setup.")
# --- END: Developer Experience Improvement ---

# Suppress TensorFlow INFO and WARNING messages to clean up console output.
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress C++ backend messages
os.environ['OTF_ENABLE_ONEDNN_OPTS'] = "0"
logging.getLogger('tensorflow').setLevel(logging.ERROR)  # Suppress Python logger messages

app = create_app()  

if __name__ == "__main__":
    # --- Security Best Practice ---
    # The `debug=True` parameter enables the Werkzeug debugger, which is a major security risk in production.
    # This check ensures that debug mode is only active when FLASK_ENV is explicitly set to 'development'.
    is_development = os.environ.get('FLASK_ENV') == 'development'
    if not is_development and app.debug:
        logging.error("SECURITY WARNING: Do not run with debug mode enabled in a production environment!")
    app.run(debug=is_development, port=5000)
