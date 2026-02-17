"""Pydantic v2 models for Waitrose products with NOVA enrichment."""

from __future__ import annotations

from pydantic import BaseModel


class Product(BaseModel):
    """A Waitrose product enriched with NOVA classification data."""

    # Scraped fields
    product_id: str | None = None
    name: str | None = None
    brand: str | None = None
    price: str | None = None
    size: str | None = None
    url: str | None = None
    category: str | None = None
    barcode: str | None = None
    image_url: str | None = None
    product_type: str | None = None
    scraped_at: str | None = None

    # NOVA enrichment from Open Food Facts
    nova_group: int | None = None
    nova_tags: list[str] | None = None
    off_name: str | None = None
    ingredients_text: str | None = None
    off_matched: bool = False