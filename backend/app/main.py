import os
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.assistant import ask_assistant
from app.database import Base, SessionLocal, engine
from app.models import Favorite, Listing, Variant, Vehicle
from app.presenters import format_listing
from app.recommendations import extract_requirements_with_ai, rank_listings, search_listings
from app.schemas import AssistantRequest, AssistantResponse, CompareRequest, ListingDetail, RecommendationRequest, SearchResults
from app.seed import seed_database

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="Carmatch AI", lifespan=lifespan)
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def listing_query():
    return (
        select(Listing)
        .join(Listing.variant)
        .join(Variant.vehicle)
        .options(joinedload(Listing.variant).joinedload(Variant.vehicle))
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/vehicles", response_model=SearchResults)
def get_vehicles(
    country_code: str = Query("IN", min_length=2, max_length=2),
    body_style: str | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    condition: str | None = None,
    search: str | None = None,
    min_price: Decimal | None = Query(None, gt=0),
    max_price: Decimal | None = Query(None, gt=0),
    sort: str = "price_asc",
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, "min_price must not exceed max_price")

    query = listing_query().where(Listing.country_code == country_code.upper(), Listing.is_active.is_(True))
    if body_style:
        query = query.where(Vehicle.body_style.ilike(f"%{body_style}%"))
    if fuel_type:
        query = query.where(Variant.fuel_type.ilike(f"%{fuel_type}%"))
    if transmission:
        query = query.where(Variant.transmission.ilike(f"%{transmission}%"))
    if condition:
        query = query.where(Listing.condition.ilike(condition))
    if min_price is not None:
        query = query.where(Listing.price >= min_price)
    if max_price is not None:
        query = query.where(Listing.price <= max_price)
    if search:
        query = query.where(or_(Vehicle.make.ilike(f"%{search}%"), Vehicle.model.ilike(f"%{search}%")))

    if sort == "price_desc":
        query = query.order_by(Listing.price.desc())
    else:
        query = query.order_by(Listing.price.asc())

    listings = list(db.scalars(query).unique())
    return SearchResults(total=len(listings), items=[format_listing(item) for item in listings])


@app.get("/api/vehicles/{listing_id}", response_model=ListingDetail)
def get_vehicle(listing_id: int, db: Session = Depends(get_db)):
    listing = db.scalar(listing_query().where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(404, "Vehicle not found")
    return format_listing(listing)


@app.post("/api/recommendations", response_model=SearchResults)
def get_recommendations(payload: RecommendationRequest, db: Session = Depends(get_db)):
    requirements, _ = extract_requirements_with_ai(payload.query, payload.country_code)
    listings = search_listings(db, requirements)
    ranked = rank_listings(listings, requirements)[:payload.limit]
    return SearchResults(
        total=len(listings),
        items=[format_listing(listing, score, reasons) for listing, score, reasons in ranked],
    )


@app.post("/api/assistant", response_model=AssistantResponse)
def car_assistant(payload: AssistantRequest, db: Session = Depends(get_db)):
    return ask_assistant(db, payload)


@app.post("/api/compare", response_model=list[ListingDetail])
def compare_vehicles(payload: CompareRequest, db: Session = Depends(get_db)):
    if len(set(payload.listing_ids)) != len(payload.listing_ids):
        raise HTTPException(422, "Choose different cars to compare")

    listings = db.scalars(listing_query().where(Listing.id.in_(payload.listing_ids))).unique().all()
    listings_by_id = {listing.id: listing for listing in listings}
    if len(listings_by_id) != len(payload.listing_ids):
        raise HTTPException(404, "One or more cars were not found")
    return [format_listing(listings_by_id[item_id]) for item_id in payload.listing_ids]


@app.get("/api/saved", response_model=list[ListingDetail])
def get_saved_vehicles(db: Session = Depends(get_db)):
    favorites = db.scalars(
        select(Favorite).options(joinedload(Favorite.listing).joinedload(Listing.variant).joinedload(Variant.vehicle))
    ).all()
    return [format_listing(favorite.listing) for favorite in favorites]


@app.post("/api/saved/{listing_id}", status_code=201)
def save_vehicle(listing_id: int, db: Session = Depends(get_db)):
    if db.get(Listing, listing_id) is None:
        raise HTTPException(404, "Vehicle not found")
    if db.get(Favorite, listing_id) is None:
        db.add(Favorite(listing_id=listing_id))
        db.commit()
    return {"saved": True, "listing_id": listing_id}


@app.delete("/api/saved/{listing_id}", status_code=204)
def remove_saved_vehicle(listing_id: int, db: Session = Depends(get_db)):
    favorite = db.get(Favorite, listing_id)
    if favorite is not None:
        db.delete(favorite)
        db.commit()
