from pydantic import BaseModel, Field, field_validator
from typing import Any


class WaitroseProduct(BaseModel):
    """A Waitrose product enriched with NOVA classification from OpenFoodFacts."""

    # From scraped data (Part A)
    product_id: str = Field(description="Waitrose line number")
    name: str = Field(description="Product name as displayed on Waitrose website")
    brand: str | None = Field(default=None, description="Brand name")
    price: str = Field(description="Display price (e.g., '£2.20')")
    size: str | None = Field(default=None, description="Weight or quantity (e.g., '400g')")
    url: str = Field(description="Full URL to product page on waitrose.com")
    category: str = Field(description="Waitrose category slug (e.g., 'blueberries')")
    barcode: str | None = Field(default=None, description="EAN barcode for OpenFoodFacts matching")
    image_url: str | None = Field(default=None, description="Product image URL")
    product_type: str | None = Field(default=None, description="Waitrose product type")
    scraped_at: str = Field(description="ISO timestamp when product was scraped")

    # From enrichment (Part B)
    nova_group: int | None = Field(
        default=None,
        ge=1,
        le=4,
        description="NOVA classification (1-4) from OpenFoodFacts, None if not matched"
    )
    nova_group_name: str | None = Field(
        default=None,
        description="NOVA group descriptive name"
    )
    off_matched: bool = Field(description="Whether product was found in OpenFoodFacts")
    enriched_at: str = Field(description="ISO timestamp when enrichment was performed")

    # Validators to convert pandas types to strings
    @field_validator('product_id', 'barcode', mode='before')
    @classmethod
    def convert_to_string(cls, v: Any) -> str:
        """Convert integers to strings for IDs and barcodes."""
        return str(v)

    @field_validator('scraped_at', 'enriched_at', mode='before')
    @classmethod
    def convert_timestamp(cls, v: Any) -> str:
        """Convert pandas Timestamp objects to ISO format strings."""
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        return str(v)

    @field_validator('nova_group', mode='before')
    @classmethod
    def convert_nan(cls, v: Any) -> int | None:
        """Convert NaN (from pandas) to None."""
        if v != v:  # NaN is the only value not equal to itself
            return None
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_id": "805332",
                    "name": "Waitrose Blueberries",
                    "brand": "Waitrose Ltd",
                    "price": "£4.60",
                    "size": "360g",
                    "url": "https://www.waitrose.com/ecom/products/waitrose-blueberries/805332-665151-665152",
                    "category": "blueberries",
                    "barcode": "5000169520468",
                    "image_url": "https://ecom-su-static-prod.wtrecom.com/images/products/11/LN_805332_BP_11.jpg",
                    "product_type": "G",
                    "scraped_at": "2026-02-15T02:36:08.860147",
                    "nova_group": 1,
                    "nova_group_name": "Unprocessed or minimally processed",
                    "off_matched": True,
                    "enriched_at": "2026-02-28T12:00:00"
                }
            ]
        }
    }
