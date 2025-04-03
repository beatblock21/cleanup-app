from flask import Flask
from .config import Config  # Import your config class

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)  # Load config

    # Import blueprints here to avoid circular imports
    from myapp.routes import main_bp  # Example blueprint

    # Register blueprints
    app.register_blueprint(main_bp)

    return app  # <-- Must return the app instance!