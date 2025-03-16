# config.py

class Config:
    SECRET_KEY = 'your_secret_key'  # Replace with your actual secret key
    SQLALCHEMY_DATABASE_URI = 'sqlite:///your-database.db'  # Example: SQLite
    SQLALCHEMY_TRACK_MODIFICATIONS = False


SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "connect_args": {"check_same_thread": False}
}
