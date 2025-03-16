# myapp/app_models.py
from datetime import datetime
from myapp.app_factory import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='normal')  # 'normal', 'admin', or 'technical'
    
    litter_hotspots = db.relationship('LitterHotspot', backref='user', lazy=True)
    bin_statuses = db.relationship('BinStatus', backref='user', lazy=True)  # To associate bin statuses with users

    def set_password(self, password):
        """Generate hashed password and store it."""
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f'<User {self.username}>'
    
    @property
    def unread_notifications_count(self):
        """Count unread notifications for the user."""
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()

class LitterHotspot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_reported = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")  # e.g., pending, resolved
    image_url = db.Column(db.String(255), nullable=True)  # New field for storing image URL
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Reporter

    def __repr__(self):
        return f'<LitterHotspot {self.location}>'
    

class ReportForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    description = TextAreaField('Description')
    image = FileField('Upload Image')
    submit = SubmitField('Submit')    

class DispatchForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    submit = SubmitField('Dispatch')


class BinStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bin_location = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="NOT_FULL")  # e.g., FULL, HALF_FULL, NOT_FULL
    last_checked = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Maintainer
 


    # Optionally, you could define status as constants for better control
    STATUS_FULL = "FULL"
    STATUS_HALF_FULL = "HALF_FULL"
    STATUS_NOT_FULL = "NOT_FULL"

    def __repr__(self):
        return f"<BinStatus {self.bin_location} - {self.status}>"
class Dispatch(db.Model):
    __tablename__ = 'dispatches'
    
    id = db.Column(db.Integer, primary_key=True)
    litter_hotspot_id = db.Column(db.Integer, db.ForeignKey('litter_hotspot.id'), nullable=False)
    truck_id = db.Column(db.Integer, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    dispatched_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Pending")

class Truck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False)  # Example field
    litter_hotspot_id = db.Column(db.Integer, db.ForeignKey('litter_hotspot.id'))  # Foreign key to LitterHotspot
    is_dispatched = db.Column(db.Boolean, nullable=False)
    # Relationship to LitterHotspot
    litter_hotspot = db.relationship('LitterHotspot', backref=db.backref('trucks', lazy=True))  # Changed backref name for clarity

    def __repr__(self):
        return f'<Truck {self.id}, Status: {self.status}, Hotspot ID: {self.litter_hotspot_id}>'

class DispatchLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('truck.id'))
    location = db.Column(db.String(255))
    dispatched_at = db.Column(db.DateTime)
    
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')

def update_bin_status(bin_id, status):
    bin = BinStatus.query.get(bin_id)
    bin.status = status
    db.session.commit()

    if status == 'full':
        # Create a notification for a default user (e.g., admin)
        default_user_id = 1  # Assuming '1' is the ID of an admin user
        notification = Notification(
            user_id=default_user_id,  # Set this to a valid user ID
            message=f"Bin {bin.id} is full. Please attend to it."
        )
        db.session.add(notification)
        db.session.commit()


def dispatch_truck_to_hotspot(hotspot_id):
    # Dispatch logic...
    
    hotspot = LitterHotspot.query.get(hotspot_id)
    notification = Notification(
        user_id=hotspot.user_id,  # Notify the user who reported the hotspot
        message=f"A truck has been dispatched to your hotspot report at {hotspot.location}."
    )
    db.session.add(notification)
    db.session.commit()

def review_hotspot(hotspot_id):
    hotspot = LitterHotspot.query.get(hotspot_id)
    # Admin review logic...
    
    notification = Notification(
        user_id=hotspot.user_id,  # Notify the user who reported the hotspot
        message=f"Your hotspot report at {hotspot.location} has been reviewed by an admin."
    )
    db.session.add(notification)
    db.session.commit()
def create_notification(message, user_id):
    notification = Notification(
        user_id=user_id,
        message=message
    )
    db.session.add(notification)
    db.session.commit()

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # ID of the report
    # Add other fields like bin status, user ID, etc.
    bin_location = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    last_checked = db.Column(db.DateTime, nullable=False)
    
