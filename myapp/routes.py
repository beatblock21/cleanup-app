from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from functools import wraps
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import json
import logging
import requests
from flask import current_app
import serial
import time
import threading
from serial.tools import list_ports
from dataclasses import dataclass
from serial import Serial, SerialException
from typing import Optional, Dict
# Import models and db here to avoid circular imports
from myapp.app_models import User, LitterHotspot, BinStatus, Dispatch, Notification, Truck, create_notification
from myapp.app_factory import db
from flask_wtf import FlaskForm

bp = Blueprint('main', __name__)

# Define the upload folder (ensure it exists)
UPLOAD_FOLDER = r"C:\Users\shred\Documents\kazi\uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Flash message and redirect utility
def flash_and_redirect(message, endpoint, category='success'):
    flash(message, category)
    return redirect(url_for(endpoint))

# Decorator to ensure the user is an admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Create notifications for multiple users
def create_notifications(user_ids, message):
    """Create notifications for multiple users."""
    for user_id in user_ids:
        notification = Notification(user_id=user_id, message=message)
        db.session.add(notification)
    db.session.commit()

def load_mock_trucks(filename='mock_trucks.json'):
    with open(filename, 'r') as f:
        return json.load(f)

# Home route
@bp.route('/')
@login_required
def home():
    # Count unread notifications
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template('home.html', unread_count=unread_count)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SERIAL_READ_INTERVAL = 0.1
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}  # Moved from original

# Modified admin dashboard route
@bp.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_dashboard():
    from .forms import DispatchTruckForm, BinStatusUpdateForm

    dispatch_form = DispatchTruckForm()
    bin_status_form = BinStatusUpdateForm()

    if dispatch_form.validate_on_submit():
        location = dispatch_form.location.data
        litter_hotspot_id = dispatch_form.hotspot_id.data
        truck_id = dispatch_form.truck_id.data

        if not location or not litter_hotspot_id or not truck_id:
            flash("Location, hotspot ID, and truck ID are required.", "danger")
        else:
            result = dispatch_truck(location, litter_hotspot_id, truck_id)
            flash(result['message'], result['category'])
        
        return redirect(url_for('main.admin_dashboard'))

    return render_template("admin_dashboard.html", 
                           dispatch_form=dispatch_form, 
                           bin_status_form=bin_status_form)

# Function to handle dispatching trucks
def dispatch_truck(location, litter_hotspot_id, truck_id):
    try:
        location_data = json.loads(location)
        lat = location_data['lat']
        lng = location_data['lng']
    except (ValueError, KeyError) as e:
        logging.error(f"Invalid location data provided: {str(e)}")
        return {'success': False, 'message': "Invalid location data provided.", 'category': 'danger'}

    # Validate that the hotspot and truck IDs are valid
    hotspot = LitterHotspot.query.get(litter_hotspot_id)
    if not hotspot:
        logging.error("Hotspot not found.")
        return {'success': False, 'message': "Hotspot not found.", 'category': 'danger'}

    try:
        with db.session.begin():
            # Create a dispatch record
            dispatch = Dispatch(litter_hotspot_id=litter_hotspot_id, truck_id=truck_id, latitude=lat, longitude=lng)
            db.session.add(dispatch)

            # Create notification for the user who reported the hotspot
            create_notification(hotspot.user_id, f"A truck has been dispatched to your reported litter hotspot at Lat: {lat}, Lng: {lng}.")

        logging.info("Truck dispatched successfully.")
        return {'success': True, 'message': 'Truck dispatched successfully!', 'category': 'success'}
    except Exception as e:
        logging.error(f"Error dispatching truck: {str(e)}")
        return {'success': False, 'message': 'Error dispatching truck!', 'category': 'danger'}

from sqlalchemy.exc import SQLAlchemyError

@bp.route('/dispatch_trucks', methods=['GET', 'POST'])
@login_required
def dispatch_trucks():
    from .forms import DispatchTruckForm
    dispatch_form = DispatchTruckForm()
    
    if request.method == 'POST':
        truck_id = request.form.get('truck_id')
        location = request.form.get('location')

        if not truck_id or not location:
            flash('Truck ID and location are required.', 'dispatch')
            return redirect(url_for('main.dispatch_trucks'))

        try:
            # Directly get the truck by ID
            truck = Truck.query.get(truck_id)
            
            if not truck:
                flash('Truck not found.', 'dispatch')
                return redirect(url_for('main.dispatch_trucks'))

            if truck.is_dispatched:
                flash('Truck is already dispatched.', 'dispatch')
                return redirect(url_for('main.dispatch_trucks'))

            # Force update status and location
            truck.is_dispatched = True
            truck.location = location

            # Commit changes immediately
            db.session.commit()

            flash(f'Truck {truck.id} successfully dispatched to {location}.', 'dispatch')
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error dispatching truck: {str(e)}', 'dispatch')

    # Retrieve all trucks
    trucks = Truck.query.all()
    return render_template('dispatch_trucks.html', trucks=trucks, dispatch_form=dispatch_form)
# Manage users route
@bp.route("/manage_users", methods=["GET", "POST"])
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str)

    # Build a query to search users
    query = User.query
    if search_query:
        query = query.filter(
            (User.username.ilike(f"%{search_query}%")) |
            (User.email.ilike(f"%{search_query}%"))
        )
 # Create a simple form just for the CSRF token
    csrf_form = FlaskForm()
    # Paginate the results (showing 10 users per page)
    users = query.paginate(page=page, per_page=10)
    return render_template("manage_users.html", users=users, search_query=search_query, csrf_form=csrf_form)

# Route to edit a user
@bp.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    from .forms import UserManagementForm
    user = User.query.get_or_404(user_id)
    form = UserManagementForm(obj=user)  # Create form instance with user data

    if form.validate_on_submit():
        user.username = form.username.data
        user.role = form.role.data
        db.session.commit()
        return flash_and_redirect("User updated successfully!", "main.manage_users")

    return render_template("edit_user.html", form=form, user=user)  # Pass form to the template

# Route to delete a user
@bp.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return flash_and_redirect("User deleted successfully!", "main.manage_users")

# Function to get coordinates from location name using Google Maps Geocoding API
def get_coordinates(location_name):
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': location_name,
        'key': 'AIzaSyChl9j-HQ8uVlzHcaZkBqTzZTENOHPMTnQ'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        if data['status'] == 'OK' and data['results']:
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
    except requests.RequestException as e:
        logging.error(f"Error fetching coordinates: {str(e)}")
    return None, None  # Location not found

@bp.route('/report_hotspot', methods=['GET', 'POST'])
@login_required
def report_hotspot():
    from .forms import LitterHotspotForm
    form = LitterHotspotForm()

    if form.validate_on_submit():
        logging.info("Report hotspot endpoint hit")
        
        try:
            # Handle the file upload
            if 'image' not in request.files or request.files['image'].filename == '':
                flash('Please select an image file', 'error')
                return redirect(url_for('main.report_hotspot'))

            file = request.files['image']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                logging.info(f"Saving file to {file_path}")
                file.save(file_path)

                location_name = form.location.data
                logging.info(f"Location name received: {location_name}")
                
                latitude, longitude = get_coordinates(location_name)
                if latitude is None or longitude is None:
                    flash('Could not find coordinates for this location', 'error')
                    return redirect(url_for('main.report_hotspot'))

                description = form.description.data or "Reported Hotspot"
                image_url = f"/uploads/{filename}"

                # Create new litter hotspot
                new_hotspot = LitterHotspot(
                    location=f"Lat: {latitude}, Lng: {longitude}",
                    description=description,
                    date_reported=datetime.utcnow(),
                    user_id=current_user.id,
                    image_url=image_url
                )
                db.session.add(new_hotspot)
                
                # Notify admins
                admin_users = User.query.filter_by(role='admin').all()
                for admin in admin_users:
                    notification = Notification(
                        user_id=admin.id,
                        message=f"New litter hotspot reported at {new_hotspot.location}.",
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(notification)

                db.session.commit()
                logging.info("Hotspot reported successfully")
                
                # Redirect to success page
                return render_template('report_hotspot_success.html')

            flash('Invalid file type', 'error')
            return redirect(url_for('main.report_hotspot'))

        except Exception as e:
            logging.error(f"Error in report_hotspot: {str(e)}")
            db.session.rollback()
            flash('An error occurred while reporting the hotspot', 'error')
            return redirect(url_for('main.report_hotspot'))

    return render_template('report_hotspot_form.html', form=form)

# Remove or modify the report_hotspot_success route since we're now handling success in the main route
# @bp.route('/report_hotspot_success', methods=['GET'])
# @login_required
# def report_hotspot_success():
#     return render_template('report_hotspot_success.html')

@bp.route('/report_hotspot_success', methods=['GET'])
@login_required
def report_hotspot_success():
    from .forms import LitterHotspotForm
    form = LitterHotspotForm()  # Create an instance of the form
    return render_template('report_hotspot_success.html',form=form)  # This is the confirmation page

# Function to create notification
def create_notification(message, user_id):
    notification = Notification(
        user_id=user_id,
        message=message
    )
    db.session.add(notification)
    db.session.commit()

from .forms import LoginForm

# Login route
@bp.route("/login", methods=["GET", "POST"])
def login():
     form = LoginForm()
     if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password", "danger")
            return redirect(url_for("main.login"))

        login_user(user)
        flash("Login successful!", "success")
        return redirect(url_for("main.home"))

     return render_template("login.html",form=form)

from .forms import RegisterForm
# Registration route
@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()  # Instantiate the form object
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        role = "normal"  # Default role
        if email.endswith("@admin.com"):  # Placeholder condition for admin
            role = "admin"

        user = User(username=username, email=email, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        flash("Registration successful!", "success")
        return redirect(url_for("main.home"))

    return render_template("register.html", form=form) 

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))

class SimpleForm(FlaskForm):
    pass  # An empty form just for the CSRF token

# Global variable to store the latest bin status data
latest_bin_status = {'distance': 'N/A', 'bin_status': 'N/A'}

@bp.route('/notifications')
@login_required
def notifications():
    # Fetch all notifications for the current user
    notifications = Notification.query.filter_by(user_id=current_user.id).all()
    form = SimpleForm()  # Create a form instance
    return render_template('notifications.html', notifications=notifications, form=form)  # Pass the form

@bp.route('/notifications/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
        flash('Notification marked as read.', 'success')
    else:
        flash('You do not have permission to mark this notification as read.', 'danger')
    return redirect(url_for('main.notifications'))


@bp.route('/realtime_bin_status', methods=['GET'])
@login_required
@admin_required
def realtime_bin_status():
    global latest_bin_status
    return jsonify(latest_bin_status)

@bp.route("/hotspots")
@login_required
def view_hotspots():
    if current_user.role not in ['admin', 'technical']:
        flash("Access forbidden.", "danger")
        return redirect(url_for("main.home"))
    
    hotspots = LitterHotspot.query.all()
    return render_template("hotspots.html", hotspots=hotspots)

@bp.route('/approve_report/<int:hotspot_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def approve_report(hotspot_id):
    hotspot = LitterHotspot.query.get_or_404(hotspot_id)
    if hotspot.status == 'pending':
        hotspot.status = 'approved'
        db.session.commit()
        flash('Hotspot approved successfully.', 'success')
    else:
        flash('Hotspot is already approved.', 'info')
    return redirect(url_for('main.view_hotspots'))

@bp.route('/update_gps', methods=['POST'])
def update_gps():
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    # Update your database or perform other actions with the GPS data
    # Example: Update a truck's location in the database
    truck = Truck.query.get(data.get('truck_id'))
    if truck:
        truck.latitude = latitude
        truck.longitude = longitude
        db.session.commit()

    return jsonify({'success': True})