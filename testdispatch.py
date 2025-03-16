from myapp.app_factory import create_app, db  # Import your app factory and database instance
from myapp.app_models import Truck    # Import the Truck model
import json

# Create the application and push the app context
app = create_app()
with app.app_context():
    # Load the mock truck data from JSON
    with open('mock_trucks.json', 'r') as f:
        mock_trucks = json.load(f)

    # Add the mock truck data to the database
    for truck in mock_trucks:
        new_truck = Truck(id=truck['id'], status='default_status', is_dispatched=truck['is_dispatched'])
        db.session.add(new_truck)

    # Commit the session
    db.session.commit()
    print("Mock trucks added to the database.")
