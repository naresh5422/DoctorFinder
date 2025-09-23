import os
import logging
import warnings
from app.main import create_app
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
warnings.filterwarnings("ignore", message="`resume_download` is deprecated and will be removed in version 1.0.0.*")
env_loaded = load_dotenv()
if env_loaded:
    logging.info("✅ '.env' file found and loaded by the application.")
    if os.getenv('MAIL_SERVER') == 'smtp.gmail.com':
        mail_password = os.getenv('MAIL_PASSWORD', '')
        if ' ' in mail_password or (mail_password and len(mail_password) != 16):
             logging.warning("   -> ⚠️  Using Gmail SMTP. Ensure 'MAIL_PASSWORD' is a 16-character App Password, not your regular Google password. Generate one at https://myaccount.google.com/apppasswords")
    db_url = os.getenv('DATABASE_URL', '')
    flask_env = os.getenv('FLASK_ENV', 'production')
    if flask_env.lower() == 'development' and 'postgresql://' in db_url:
        logging.warning("   -> ⚠️  Development environment detected with a PostgreSQL DATABASE_URL. For local setup, this should point to your MySQL database. Check your .env file.")
else:
    logging.warning("⚠️ '.env' file not found. Application might not be configured. See README.md for setup.")
app = create_app()  

if __name__ == "__main__":
    is_development = os.environ.get('FLASK_ENV', 'production').lower() == 'development'
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=is_development)
