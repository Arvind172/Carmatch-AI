from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, Variant, Vehicle


SAMPLE_CARS = [
    ("Maruti Suzuki", "Swift", 2024, "Hatchback", "Petrol", "Automatic", "FWD", 1197, 80, 113, 5, 22.0, "km/l", "IN", "INR", 950000, "New", None, "Pune"),
    ("Hyundai", "Creta", 2024, "SUV", "Petrol", "Automatic", "FWD", 1497, 113, 144, 5, 17.4, "km/l", "IN", "INR", 1750000, "New", None, "Mumbai"),
    ("Tata", "Nexon", 2024, "SUV", "Electric", "Automatic", "FWD", None, 143, 215, 5, 325, "km/charge", "IN", "INR", 1650000, "New", None, "Bengaluru"),
    ("Honda", "City", 2023, "Sedan", "Petrol", "Automatic", "FWD", 1498, 119, 145, 5, 18.4, "km/l", "IN", "INR", 1450000, "Used", 18000, "Delhi"),
    ("Mahindra", "XUV700", 2024, "SUV", "Diesel", "Automatic", "AWD", 2198, 182, 450, 7, 16.5, "km/l", "IN", "INR", 2450000, "New", None, "Hyderabad"),
    ("Toyota", "Camry", 2024, "Sedan", "Hybrid", "Automatic", "FWD", 2487, 208, 221, 5, 51, "mpg", "US", "USD", 34500, "New", None, "Austin"),
    ("Honda", "CR-V", 2023, "SUV", "Gasoline", "Automatic", "AWD", 1498, 190, 179, 5, 29, "mpg", "US", "USD", 31500, "Used", 16000, "Seattle"),
    ("Toyota", "RAV4", 2024, "SUV", "Hybrid", "Automatic", "AWD", 2487, 219, 221, 5, 39, "mpg", "US", "USD", 36500, "New", None, "Denver"),
    ("Ford", "F-150", 2023, "Pickup", "Gasoline", "Automatic", "4WD", 2694, 325, 400, 5, 22, "mpg", "US", "USD", 42900, "Used", 22000, "Dallas"),
    ("Tesla", "Model 3", 2024, "Sedan", "Electric", "Automatic", "RWD", None, 283, 420, 5, 341, "miles/charge", "US", "USD", 38990, "New", None, "San Jose"),
    ("Subaru", "Outback", 2022, "Wagon", "Gasoline", "Automatic", "AWD", 2498, 182, 176, 5, 26, "mpg", "US", "USD", 25900, "Used", 31000, "Portland"),
    ("Kia", "Seltos", 2024, "SUV", "Petrol", "Automatic", "FWD", 1497, 158, 253, 5, 17.7, "km/l", "IN", "INR", 1550000, "New", None, "Chennai"),
]


def seed_database(db: Session) -> int:
    existing = set(db.scalars(select(Listing.source_name).where(Listing.source_name == "Carmatch illustrative sample")))
    if existing:
        return 0
    added = 0
    for make, model, year, body, fuel, transmission, drive, cc, hp, torque, seats, mileage, unit, country, currency, price, condition, odometer, city in SAMPLE_CARS:
        vehicle = db.scalar(select(Vehicle).where(Vehicle.make == make, Vehicle.model == model, Vehicle.model_year == year))
        if vehicle is None:
            vehicle = Vehicle(make=make, model=model, model_year=year, body_style=body, safety_rating=Decimal("4.0"), description=f"Illustrative {year} {make} {model} catalog record. Specifications and prices are provided for product demonstration.")
            db.add(vehicle)
            db.flush()
        variant = Variant(vehicle_id=vehicle.id, name="Sample trim", trim="Sample trim", fuel_type=fuel, transmission=transmission, drivetrain=drive, engine_displacement_cc=cc, power_hp=hp, torque_nm=torque, seating_capacity=seats, mileage_rating=mileage, mileage_rating_unit=unit, is_electric=(fuel == "Electric"))
        db.add(variant)
        db.flush()
        db.add(Listing(variant_id=variant.id, country_code=country, currency_code=currency, price=price, condition=condition, odometer_value=odometer, odometer_unit="km" if country == "IN" else "mi", city=city, region=city, source_name="Carmatch illustrative sample", source_url=None, is_sample=True))
        added += 1
    db.commit()
    return added
