from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from functools import wraps
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import json
import logging

# Import models and db here to avoid circular imports
from myapp.app_models import User, LitterHotspot, BinStatus, Dispatch, Notification, Truck, create_notification
from myapp.app_factory import db

bp = Blueprint('main', __name__)

# Admin required decorator for protected admin routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Admin dashboard route
@bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

# Route to manage users with search and pagination
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

    # Paginate the results (showing 10 users per page)
    users = query.paginate(page=page, per_page=10)

    return render_template("manage_users.html", users=users, search_query=search_query)

# Route to edit a user
@bp.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        user.username = request.form["username"]
        user.email = request.form["email"]
        user.role = request.form["role"]
        
        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("main.manage_users"))

    return render_template("edit_user.html", user=user)

# Route to delete a user
@bp.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully!", "success")
    return redirect(url_for("main.manage_users"))

# Define the upload folder (ensure it exists)
UPLOAD_FOLDER = r"C:\Users\shred\Documents\kazi\uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configure logging
logging.basicConfig(level=logging.INFO)

import requests  # Import requests for making HTTP calls

# Function to get coordinates from location name using OpenStreetMap Nominatim API
def get_coordinates(location_name):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        'q': location_name,
        'format': 'json',
        'limit': 1  # Limit to one result
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if len(data) > 0:
            latitude = data[0]['lat']
            longitude = data[0]['lon']
            return latitude, longitude
        else:
            return None, None  # Location not found
    else:
        return None, None  # Failed request

# Report Hotspot Route with location name to coordinates conversion
@bp.route("/report_hotspot", methods=["POST"])
@login_required
def report_hotspot():
    logging.info("Report hotspot endpoint hit")
    
    if 'image' not in request.files:
        logging.warning("No file part in the request")
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        logging.warning("No selected file")
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        logging.info(f"Saving file to {file_path}")
        file.save(file_path)

        # Get location name from the form
        location_name = request.form['location']
        logging.info(f"Location name received: {location_name}")

        # Convert location name to latitude and longitude
        latitude, longitude = get_coordinates(location_name)

        if latitude is None or longitude is None:
            logging.error("Failed to get coordinates for location")
            return jsonify({"error": "Invalid location data"}), 400
        
        description = request.form.get('description', "Reported Hotspot")
        image_url = f"/uploads/{filename}"

        location = f"Lat: {latitude}, Lng: {longitude}"
        logging.info(f"Location coordinates: {location}")

        new_hotspot = LitterHotspot(
            location=location,
            description=description,
            date_reported=datetime.utcnow(),
            user_id=current_user.id,
            image_url=image_url
        )

        db.session.add(new_hotspot)
        db.session.commit()
        logging.info("New litter hotspot added to the database")

        # Create a notification for admins
        admin_users = User.query.filter_by(role='admin').all()
        for admin in admin_users:
            notification = Notification(
                user_id=admin.id,
                message=f"New litter hotspot reported at {location}.",
                timestamp=datetime.utcnow()
            )
            db.session.add(notification)

        db.session.commit()
        logging.info("Notifications sent to admins")

        return jsonify({"message": "Litter hotspot reported successfully!"}), 201

    logging.warning("File type not allowed")
    return jsonify({"error": "File type not allowed"}), 400

# Route to display the form for reporting a hotspot
@bp.route("/report_hotspot", methods=["GET"])
@login_required
def report_hotspot_form():
    return render_template('report_hotspot_form.html')

# Route to view all litter hotspots (Admins and technical users)
@bp.route("/hotspots")
@login_required
def view_hotspots():
    if current_user.role not in ['admin', 'technical']:
        flash("Access forbidden.", "danger")
        return redirect(url_for("main.home"))
    
    hotspots = LitterHotspot.query.all()
    return render_template("hotspots.html", hotspots=hotspots)

# Route for admins to view bin status reports
@bp.route("/bin_status_reports")
@login_required
@admin_required
def bin_status_reports():
    bin_status_reports = BinStatus.query.all()
    return render_template("bin_status_reports.html", bin_status_reports=bin_status_reports)

@bp.route('/dispatch/truck', methods=['POST'])
@login_required
def dispatch_truck():
    # Get the location from the form
    location = request.form.get('location')
    litter_hotspot_id = request.form.get('hotspot_id')  # Make sure to pass this from the form as well

    if not location or not litter_hotspot_id:
        flash("Location and hotspot ID are required.", "danger")
        return redirect(url_for('main.admin_dashboard'))

    location_data = json.loads(location)
    lat = location_data['lat']
    lng = location_data['lng']

    # Create a dispatch record
    dispatch = Dispatch(litter_hotspot_id=litter_hotspot_id, truck_id=1, latitude=lat, longitude=lng)
    db.session.add(dispatch)
    db.session.commit()

    # Create notification for the user who reported the hotspot
    hotspot = LitterHotspot.query.get(litter_hotspot_id)  # Use the hotspot ID passed from the form
    if hotspot:
        notification = Notification(
            user_id=hotspot.user_id,
            message=f"A truck has been dispatched to your reported hotspot at {hotspot.location}.",
            timestamp=datetime.utcnow()
        )
        db.session.add(notification)

    db.session.commit()

    flash("Truck dispatched successfully!", "success")
    return redirect(url_for('main.trucks'))  # Redirect to the trucks page

@bp.route('/approve_report/<int:report_id>', methods=['POST'])
@login_required
def approve_report(report_id):
    report = LitterHotspot.query.get_or_404(report_id)
    report.status = 'Approved'
    db.session.commit()

    create_notification("Admin approved the litter report: {}".format(report.id))
    return redirect(url_for('main.reports'))




# Route for displaying notifications
@bp.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    
    return render_template("notifications.html", notifications=notifications)

# Mark notification as read
@bp.route('/notifications/read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        abort(403)

    notification.is_read = True
    db.session.commit()

    return redirect(url_for('main.dashboard'))

# Custom 403 error handler
@bp.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403

# Map route
@bp.route("/map")
@login_required
def show_map():
    return render_template("map.html")

# Home route
@bp.route("/")
def home():
    return render_template("home.html")

# Registration route
@bp.route("/register", methods=["GET", "POST"])
def register():
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

    return render_template("register.html")

# Login route
@bp.route("/login", methods=["GET", "POST"])
def login():
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

    return render_template("login.html")

# Logout route
@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))

@bp.route('/trucks', methods=['GET'])
@login_required
def trucks():
    # Query to get the available trucks
    trucks = Truck.query.all()  # Modify this query as needed
    return render_template('trucks.html', trucks=trucks)




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


