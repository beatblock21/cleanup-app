from flask import Flask
from flask_wtf.csrf import CSRFProtect
from myapp.app_factory import create_app

# Create and configure the Flask app
app = create_app()

# Initialize the CSRF protection object
csrf = CSRFProtect(app)  # Pass the app to CSRF protect directly

# Optional: Disable CSRF expiration for testing purposes
WTF_CSRF_TIME_LIMIT = None  



if __name__ == "__main__":
    app.run(debug=True)
