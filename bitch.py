# main.py

from flask import Flask, Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
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
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
import asyncio
import websockets
from aiohttp import web

# Initialize Flask app and database
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'main.login'

# Import models and db here to avoid circular imports
from myapp.app_models import User, LitterHotspot, BinStatus, Dispatch, Notification, Truck, create_notification

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

@bp.route("/hotspots")
@login_required
def view_hotspots():
    if current_user.role not in ['admin', 'technical']:
        flash("Access forbidden.", "danger")
        return redirect(url_for("main.home"))
    
    hotspots = LitterHotspot.query.all()
    return render_template("hotspots.html", hotspots=hotspots)

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
                         bin_status_form=bin_status_form,
                        )

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

@bp.route('/dispatch_trucks', methods=['GET', 'POST'])
@login_required  # Optional: Ensure only logged-in users can access this
def dispatch_trucks():
    from .forms import DispatchTruckForm
    dispatch_form = DispatchTruckForm()  # Create an instance of the form
    
    # Load mock data from JSON
    trucks = load_mock_trucks()  

    if request.method == 'POST':  # Check if the form is submitted
        if dispatch_form.validate_on_submit():
            truck_id = request.form.get('truck_id')
            location = request.form.get('location')

            # Find the truck in the database
            truck = Truck.query.get(truck_id)
            if truck and not truck.is_dispatched:  # Check if the truck exists and is available
                truck.is_dispatched = True  # Update the truck's status
                truck.location = location  # Update location if provided
                db.session.commit()  # Save changes to the database

                flash(f'Truck {truck_id} dispatched to {location}.', 'success')
            else:
                flash('Truck is already dispatched or not found.', 'danger')
        else:
            logging.error('Form validation failed')
    
    # For GET requests, retrieve all available trucks
    trucks = Truck.query.all()  # Fetch all trucks from the database
    return render_template('dispatch_trucks.html', trucks=trucks, dispatch_form=dispatch_form)  # Pass data to the template

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

# Function to get coordinates from location name using OpenStreetMap Nominatim API
def get_coordinates(location_name):
    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        'q': location_name,
        'format': 'json',
        'limit': 1  # Limit to one result
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        if data:
            latitude = data[0]['lat']
            longitude = data[0]['lon']
            return latitude, longitude
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
                logging.warning("No file part or no selected file")
                return jsonify({"error": "No file part or no selected file"}), 400

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
                    logging.error("Failed to get coordinates for location")
                    return jsonify({"error": "Invalid location data"}), 400

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
                db.session.commit()
                logging.info("New litter hotspot added to the database")

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
                logging.info("Notifications sent to admins")

                # Redirect to a confirmation page or show success message
                return redirect(url_for('main.report_hotspot_success'))  # Adjust this to your actual success page
                
            logging.warning("File type not allowed")
            return jsonify({"error": "File type not allowed"}), 400

        except Exception as e:
            logging.error(f"Error in report_hotspot: {str(e)}")
            return jsonify({"error": "An internal error occurred"}), 500

    return render_template('report_hotspot_form.html', form=form)

@bp.route('/report_hotspot_success', methods=['GET'])
@login_required
def report_hotspot_success():
    return render_template('report_hotspot.html')  # This is the confirmation page

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
def notifications():
    # Fetch all notifications for the current user
    notifications = current_user.notifications
    form = SimpleForm()  # Create a form instance
    return render_template('notifications.html', notifications=notifications, form=form)  # Pass the form

@bp.route('/realtime_bin_status', methods=['GET'])
@login_required
@admin_required
def realtime_bin_status():
    global latest_bin_status
    return jsonify(latest_bin_status)

@bp.route('/bin_dashboard')
@login_required
@admin_required
def bin_dashboard():
    return render_template('bin_dashboard.html')

class BinMonitor:
    def __init__(self, port='COM21', baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self.connected_clients = set()

    async def connect_serial(self):
        """Establish serial connection with NodeMCU"""
        try:
            self.ser = Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            print(f"[{self.get_timestamp()}] Serial connection established on {self.port}")
            return True
        except Exception as e:
            print(f"[{self.get_timestamp()}] Serial connection error: {e}")
            return False

    def get_timestamp(self):
        """Get current timestamp"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def parse_distance(self, distance_str):
        """Parse distance value from string, removing units"""
        distance_str = distance_str.replace('Distance:', '').strip()
        return float(distance_str.replace(' cm', ''))

    async def websocket_handler(self, websocket):
        """Handle WebSocket connections"""
        try:
            self.connected_clients.add(websocket)
            while True:
                if self.ser and self.ser.in_waiting:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        try:
                            parts = data.split(',')
                            if len(parts) == 2:
                                distance = self.parse_distance(parts[0])
                                bin_status = parts[1].replace('Bin Status:', '').strip()
                                
                                message = json.dumps({
                                    'distance': distance,
                                    'bin_status': bin_status,
                                    'timestamp': self.get_timestamp()
                                })
                                
                                await websocket.send(message)
                        except Exception as e:
                            print(f"Error processing data: {e}")
                await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.remove(websocket)

    async def handle_index(self, request):
        """Serve the HTML dashboard"""
        template_path = os.path.join('templates', 'index.html')
        with open(template_path, 'r') as f:
            return web.Response(text=f.read(), content_type='text/html')

    async def start_server(self):
        """Start the web and WebSocket servers"""
        if not await self.connect_serial():
            return

        app = web.Application()
        app.router.add_get('/', self.handle_index)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8080)
        
        await site.start()
        print(f"[{self.get_timestamp()}] Web server started at http://localhost:8080")
        
        # Use the websocket_handler directly without path parameter
        ws_server = await websockets.serve(self.websocket_handler, 'localhost', 8765)
        print(f"[{self.get_timestamp()}] WebSocket server started at ws://localhost:8765")
        
        await asyncio.Future()  # run forever

    def cleanup(self):
        """Clean up resources"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"[{self.get_timestamp()}] Serial connection closed")

async def main():
    monitor = BinMonitor()
    try:
        await monitor.start_server()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        monitor.cleanup()

if __name__ == "__main__":
    import asyncio
    from threading import Thread

    def run_flask():
        app.run(debug=True)

    def run_bin_monitor():
        asyncio.run(main())

    flask_thread = Thread(target=run_flask)
    bin_monitor_thread = Thread(target=run_bin_monitor)

    flask_thread.start()
    bin_monitor_thread.start()

    flask_thread.join()
    bin_monitor_thread.join() 

    # main.py

if __name__ == "__main__":
    import asyncio
    from threading import Thread

    def run_flask():
        app.run(debug=True)

    def run_bin_monitor():
        asyncio.run(main())

    flask_thread = Thread(target=run_flask)
    bin_monitor_thread = Thread(target=run_bin_monitor)

    flask_thread.start()
    bin_monitor_thread.start()

    flask_thread.join()
    bin_monitor_thread.join()