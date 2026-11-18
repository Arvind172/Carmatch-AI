from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ListingOut(ORMModel):
    id: int
    country_code: str
    currency_code: str
    price: Decimal
    condition: str
    odometer_value: int | None
    odometer_unit: str | None
    city: str | None
    region: str | None
    source_name: str | None
    source_url: str | None
    is_active: bool
    is_sample: bool


class VariantOut(ORMModel):
    id: int
    name: str
    trim: str | None
    fuel_type: str | None
    transmission: str | None
    drivetrain: str | None
    engine_displacement_cc: int | None
    engine_displacement_l: Decimal | None
    power_hp: Decimal | None
    torque_nm: Decimal | None
    seating_capacity: int | None
    mileage_rating: Decimal | None
    mileage_rating_unit: str | None
    is_electric: bool


class VehicleOut(ORMModel):
    id: int
    make: str
    model: str
    model_year: int
    generation: str | None
    body_style: str | None
    safety_rating: Decimal | None
    description: str | None


class ListingDetail(ListingOut):
    vehicle: VehicleOut
    variant: VariantOut
    match_score: int | None = None
    match_reasons: list[str] = Field(default_factory=list)


class SearchResults(BaseModel):
    total: int
    items: list[ListingDetail]


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    limit: int = Field(default=6, ge=1, le=20)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


class AssistantResponse(BaseModel):
    answer: str
    ai_enabled: bool
    items: list[ListingDetail]


class CompareRequest(BaseModel):
    listing_ids: list[int] = Field(min_length=2, max_length=4)
