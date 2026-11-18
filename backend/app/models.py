from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        Index("ix_vehicles_make_model_year", "make", "model", "model_year"),
        CheckConstraint("model_year >= 1886 AND model_year <= 2100", name="ck_vehicles_model_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    make: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    generation: Mapped[str | None] = mapped_column(String(100))
    body_style: Mapped[str | None] = mapped_column(String(50))
    safety_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    variants: Mapped[list["Variant"]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (CheckConstraint("seating_capacity IS NULL OR seating_capacity > 0", name="ck_variants_seating_capacity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    trim: Mapped[str | None] = mapped_column(String(120))
    fuel_type: Mapped[str | None] = mapped_column(String(40))
    transmission: Mapped[str | None] = mapped_column(String(40))
    drivetrain: Mapped[str | None] = mapped_column(String(40))
    engine_displacement_cc: Mapped[int | None] = mapped_column(Integer)
    engine_displacement_l: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    power_hp: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    power_kw: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    torque_nm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    seating_capacity: Mapped[int | None] = mapped_column(Integer)
    mileage_rating: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    mileage_rating_unit: Mapped[str | None] = mapped_column(String(20))
    is_electric: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="variants")
    listings: Mapped[list["Listing"]] = relationship(back_populates="variant", cascade="all, delete-orphan")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_market_price", "country_code", "currency_code", "price"),
        CheckConstraint("price >= 0", name="ck_listings_nonnegative_price"),
        CheckConstraint("condition IN ('New', 'Used')", name="ck_listings_condition"),
        CheckConstraint("odometer_value IS NULL OR odometer_value >= 0", name="ck_listings_odometer"),
        CheckConstraint("length(country_code) = 2", name="ck_listings_country_code_length"),
        CheckConstraint("length(currency_code) = 3", name="ck_listings_currency_code_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    odometer_value: Mapped[int | None] = mapped_column(Integer)
    odometer_unit: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    source_name: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    variant: Mapped["Variant"] = relationship(back_populates="listings")


class Favorite(Base):
    __tablename__ = "favorites"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    listing: Mapped["Listing"] = relationship()
