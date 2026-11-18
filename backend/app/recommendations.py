import os
import re
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Listing, Variant, Vehicle


@dataclass
class Requirements:
    country_code: str | None = None
    currency_code: str | None = None
    max_budget: Decimal | None = None
    transmission: str | None = None
    body_style: str | None = None
    fuel_type: str | None = None
    condition: str | None = None
    seating_capacity: int | None = None
    priorities: list[str] | None = None


class AIRequirements(BaseModel):
    country_code: str | None
    currency_code: str | None
    max_budget: float | None
    transmission: str | None
    body_style: str | None
    fuel_type: str | None
    condition: str | None
    seating_capacity: int | None
    priorities: list[str]


def parse_requirements(query: str, country_code: str | None = None) -> Requirements:
    text = query.lower().replace(",", "")
    country = country_code.upper() if country_code else None
    currency = None
    budget = None

    budget_matches = list(re.finditer(r"(₹|rs\.?\s*|inr\s*|\$|usd\s*)(\d+(?:\.\d+)?)\s*(lakhs?|laks?|lacs?|crores?|cr|k|thousand|millions?|m)?", text))
    budget_match = budget_matches[-1] if budget_matches else None
    if budget_match:
        symbol, amount, unit = budget_match.groups()
        amount = Decimal(amount)
        unit = unit or ""
        if symbol.strip() in ("₹", "rs", "rs.", "inr"):
            country, currency = "IN", "INR"
            multiplier = Decimal("10000000") if unit in ("crore", "crores", "cr") else Decimal("100000") if unit in ("lakh", "lakhs", "lak", "laks", "lac", "lacs") else 1
        else:
            country, currency = "US", "USD"
            multiplier = Decimal("1000000") if unit in ("million", "millions", "m") else Decimal("1000") if unit in ("k", "thousand") else 1
        budget = amount * multiplier
    else:
        plain_budget = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(lakhs?|laks?|lacs?|crores?|cr|k|thousand|millions?|m)\b", text))
        if plain_budget:
            amount, unit = plain_budget[-1].groups()
            amount = Decimal(amount)
            if unit in ("lakh", "lakhs", "lak", "laks", "lac", "lacs", "crore", "crores", "cr"):
                country, currency = "IN", "INR"
                multiplier = Decimal("10000000") if unit in ("crore", "crores", "cr") else Decimal("100000")
            else:
                currency = "USD" if country == "US" else "INR" if country == "IN" else None
                multiplier = Decimal("1000000") if unit in ("million", "millions", "m") else Decimal("1000")
            budget = amount * multiplier
        else:
            country_currency = {"IN": "INR", "US": "USD"}
            currency = country_currency.get(country)

    def last_choice(options):
        matches = []
        for word, value in options:
            matches.extend((match.start(), value) for match in re.finditer(rf"\b{word}\b", text))
        return max(matches)[1] if matches else None

    transmission = last_choice((("automatic", "Automatic"), ("auto", "Automatic"), ("cvt", "Automatic"), ("manual", "Manual")))
    body_style = last_choice((("suv", "SUV"), ("sedan", "Sedan"), ("hatchback", "Hatchback"), ("pickup", "Pickup")))
    fuel_type = last_choice((("electric", "Electric"), ("hybrid", "Hybrid"), ("diesel", "Diesel"), ("petrol", "Petrol"), ("gasoline", "Gasoline")))
    condition = last_choice((("used", "Used"), ("new", "New")))

    seat_matches = list(re.finditer(r"(?:family of|seats?)\s+(\d+|five|six|seven|eight)", text))
    seat_match = seat_matches[-1] if seat_matches else None
    seat_words = {"five": 5, "six": 6, "seven": 7, "eight": 8}
    seats = seat_words.get(seat_match.group(1), int(seat_match.group(1)) if seat_match and seat_match.group(1).isdigit() else None) if seat_match else None
    priorities = [word for word in ("mileage", "safe", "reliable", "low maintenance") if word in text]
    if re.search(r"\b(cheap|cheaper|affordable|inexpensive|low-cost|budget-friendly)\b", text):
        priorities.append("price")

    return Requirements(country, currency, budget, transmission, body_style, fuel_type, condition, seats, priorities)


def extract_requirements_with_ai(query: str, country_code: str | None = None) -> tuple[Requirements, bool]:
    if not os.getenv("OPENAI_API_KEY"):
        return parse_requirements(query, country_code), False

    try:
        from openai import OpenAI

        result = OpenAI().beta.chat.completions.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Extract only the user's explicit car search requirements. Convert budget shorthand to numeric amounts in INR or USD. Return null for unknown fields."},
                {"role": "user", "content": f"Selected market: {country_code or 'unspecified'}\nRequest: {query}"},
            ],
            response_format=AIRequirements,
        )
        values = result.choices[0].message.parsed
        if values is None:
            return parse_requirements(query, country_code), False

        data = values.model_dump()
        if data["max_budget"] is not None:
            data["max_budget"] = Decimal(str(data["max_budget"]))
        requirements = Requirements(**data)
        if requirements.country_code:
            requirements.country_code = requirements.country_code.upper()
        if requirements.currency_code:
            requirements.currency_code = requirements.currency_code.upper()
        return requirements, True
    except Exception:
        return parse_requirements(query, country_code), False


def search_listings(db: Session, requirements: Requirements) -> list[Listing]:
    query = (
        select(Listing)
        .join(Listing.variant)
        .join(Variant.vehicle)
        .options(joinedload(Listing.variant).joinedload(Variant.vehicle))
        .where(Listing.is_active.is_(True))
    )
    if requirements.country_code:
        query = query.where(Listing.country_code == requirements.country_code)
    if requirements.currency_code:
        query = query.where(Listing.currency_code == requirements.currency_code)
    if requirements.max_budget is not None:
        query = query.where(Listing.price <= requirements.max_budget)
    if requirements.transmission:
        query = query.where(Variant.transmission.ilike(f"%{requirements.transmission}%"))
    if requirements.body_style:
        query = query.where(Vehicle.body_style.ilike(f"%{requirements.body_style}%"))
    if requirements.fuel_type:
        query = query.where(Variant.fuel_type.ilike(f"%{requirements.fuel_type}%"))
    if requirements.condition:
        query = query.where(Listing.condition == requirements.condition)
    if requirements.seating_capacity:
        query = query.where(Variant.seating_capacity >= requirements.seating_capacity)
    return list(db.scalars(query.order_by(Listing.price).limit(100)).unique())


def format_price(amount: Decimal, currency: str) -> str:
    if currency == "INR":
        if amount >= Decimal("10000000"):
            value = amount / Decimal("10000000")
            formatted = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"₹{formatted} crore"
        if amount >= Decimal("100000"):
            value = amount / Decimal("100000")
            formatted = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"₹{formatted} lakh"
        return f"₹{amount:,.0f}"
    return f"${amount:,.0f}"


def has_search_preferences(requirements: Requirements) -> bool:
    return any((
        requirements.max_budget,
        requirements.transmission,
        requirements.body_style,
        requirements.fuel_type,
        requirements.condition,
        requirements.seating_capacity,
        requirements.priorities,
    ))


def rank_listings(listings: list[Listing], requirements: Requirements) -> list[tuple[Listing, int, list[str]]]:
    ranked = []
    for listing in listings:
        variant = listing.variant
        vehicle = variant.vehicle
        score = 50
        reasons = []

        if requirements.max_budget is not None:
            score += 15
            under_budget = requirements.max_budget - listing.price
            reasons.append(
                f"Listed at {format_price(listing.price, listing.currency_code)}, "
                f"{format_price(under_budget, listing.currency_code)} under your "
                f"{format_price(requirements.max_budget, listing.currency_code)} budget"
            )
        else:
            if "price" in (requirements.priorities or []):
                reasons.append(f"Lower-priced option at {format_price(listing.price, listing.currency_code)}")
            else:
                reasons.append(f"Sample listing price: {format_price(listing.price, listing.currency_code)}")
        if requirements.transmission:
            score += 10
            reasons.append(f"{variant.transmission} transmission, as requested")
        if requirements.body_style:
            score += 10
            reasons.append(f"{vehicle.body_style} body style, as requested")
        if requirements.fuel_type:
            score += 10
            reasons.append(f"{variant.fuel_type} powertrain, as requested")
        if requirements.condition:
            reasons.append(f"Listed as {listing.condition.lower()}, as requested")
        if requirements.seating_capacity:
            score += 10
            reasons.append(
                f"Seats {variant.seating_capacity}, meeting your need for "
                f"at least {requirements.seating_capacity}"
            )
        if "mileage" in (requirements.priorities or []) and variant.mileage_rating:
            reasons.append(
                f"Catalog efficiency figure: {variant.mileage_rating} "
                f"{variant.mileage_rating_unit}"
            )
            score += min(int(variant.mileage_rating / 5), 10)
        if "safe" in (requirements.priorities or []) and vehicle.safety_rating:
            reasons.append(f"Sample safety rating: {vehicle.safety_rating}/5")
            score += 5
        for priority in ("reliable", "low maintenance"):
            if priority in (requirements.priorities or []):
                reasons.append("Reliability and maintenance data are not included in this sample catalog")
                break
        if not has_search_preferences(requirements):
            reasons.append("Shown as one of the lowest-priced sample listings in this market")

        ranked.append((listing, min(score, 100), reasons))

    return sorted(ranked, key=lambda item: (-item[1], item[0].price))
