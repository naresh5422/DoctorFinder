import os
import logging

# Suppress TensorFlow INFO and WARNING messages to clean up console output.
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress C++ backend messages
logging.getLogger('tensorflow').setLevel(logging.ERROR)  # Suppress Python logger messages

from app.main import create_app

app = create_app()  
if __name__ == "__main__":
    app.run(debug=True, port=5000)
