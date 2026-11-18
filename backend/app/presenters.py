from app.models import Listing
from app.schemas import ListingDetail, ListingOut, VariantOut, VehicleOut


def format_listing(listing: Listing, score: int | None = None, reasons: list[str] | None = None) -> ListingDetail:
    listing_fields = ListingOut.model_validate(listing).model_dump()
    return ListingDetail(
        **listing_fields,
        vehicle=VehicleOut.model_validate(listing.variant.vehicle),
        variant=VariantOut.model_validate(listing.variant),
        match_score=score,
        match_reasons=reasons or [],
    )
