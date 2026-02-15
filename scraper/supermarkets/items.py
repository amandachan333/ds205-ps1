# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ProductItem(scrapy.Item):
    """Data structure for scraped grocery products.

    Fields are limited to what's needed for the product catalogue and
    for matching against Open Food Facts (barcode, name, brand).
    Nutrition/ingredients come from Open Food Facts in Part B."""

    product_id = scrapy.Field()
    name = scrapy.Field()
    brand = scrapy.Field()
    price = scrapy.Field()
    size = scrapy.Field()
    url = scrapy.Field()
    category = scrapy.Field()
    barcode = scrapy.Field()
    image_url = scrapy.Field()
    product_type = scrapy.Field()
    scraped_at = scrapy.Field()