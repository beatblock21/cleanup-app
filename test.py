from myapp.app_factory import create_app, db
from myapp.app_models import LitterHotspot, BinStatus
from datetime import datetime

app = create_app()

with app.app_context():
    # Testing LitterHotspot
    print("Testing LitterHotspot...")
    
    # Create
    hotspot = LitterHotspot(
        location="Park",
        description="Lots of trash",
        date_reported=datetime.utcnow(),
        user_id=1  # Replace with an existing user ID or adjust as needed
    )
    db.session.add(hotspot)
    db.session.commit()
    
    # Retrieve and verify
    retrieved_hotspot = LitterHotspot.query.filter_by(location="Park").first()
    assert retrieved_hotspot is not None
    assert retrieved_hotspot.description == "Lots of trash"
    print("LitterHotspot Create and Retrieve successful!")
    
    # Update
    retrieved_hotspot.description = "Updated description"
    db.session.commit()
    updated_hotspot = LitterHotspot.query.filter_by(location="Park").first()
    assert updated_hotspot.description == "Updated description"
    print("LitterHotspot Update successful!")
    
    # Delete
    db.session.delete(updated_hotspot)
    db.session.commit()
    deleted_hotspot = LitterHotspot.query.filter_by(location="Park").first()
    assert deleted_hotspot is None
    print("LitterHotspot Delete successful!")
    
    # Testing BinStatus
    print("Testing BinStatus...")
    
    # Create
    bin_status = BinStatus(
        bin_location="Street Corner",
        status="not_full",
        last_checked=datetime.utcnow(),
        user_id=1  # Replace with an existing user ID or adjust as needed
    )
    db.session.add(bin_status)
    db.session.commit()
    
    # Retrieve and verify
    retrieved_bin_status = BinStatus.query.filter_by(bin_location="Street Corner").first()
    assert retrieved_bin_status is not None
    assert retrieved_bin_status.status == "not_full"
    print("BinStatus Create and Retrieve successful!")
    
    # Update
    retrieved_bin_status.status = "full"
    db.session.commit()
    updated_bin_status = BinStatus.query.filter_by(bin_location="Street Corner").first()
    assert updated_bin_status.status == "full"
    print("BinStatus Update successful!")
    
    # Delete
    db.session.delete(updated_bin_status)
    db.session.commit()
    deleted_bin_status = BinStatus.query.filter_by(bin_location="Street Corner").first()
    assert deleted_bin_status is None
    print("BinStatus Delete successful!")

    print("Database functionality tests completed successfully!")
