from myapp.app_factory import create_app, db
from myapp.app_models import User

app = create_app()

with app.app_context():
    # Create an admin user
    admin_user = User(username="admin", email="admin@example.com", role="admin")
    admin_user.set_password("your_admin_password")

    db.session.add(admin_user)
    db.session.commit()

    print("Admin user created!")
