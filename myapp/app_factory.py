from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Define the upload folder path
UPLOAD_FOLDER = 'C:/Users/shred/Documents/kazi/uploads'

def create_app():
    # Create and configure the Flask app
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object('config.Config')  # Load configuration from config file
    
    # Set the upload folder in the app configuration
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Initialize CSRF protection
    
    # Import blueprints to register routes
    from myapp.routes import bp as main_routes

    app.register_blueprint(main_routes)
    
    # Define user loader for Flask-Login
    from myapp.app_models import User  # Import models after db initialization
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Set login view for unauthorized users
    login_manager.login_view = 'main.login'

    return app
