# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ProductItem(scrapy.Item):
    """Data structure for scraped grocery products"""
    url = scrapy.Field()
    product_id = scrapy.Field()
    name = scrapy.Field()
    price = scrapy.Field()
    description = scrapy.Field()
    ingredients = scrapy.Field()
    nutritional_info = scrapy.Field()
    category = scrapy.Field()
    brand = scrapy.Field()
    image_url = scrapy.Field()
    scraped_at = scrapy.Field()
    barcode = scrapy.Field()
    allergens = scrapy.Field()
    product_type = scrapy.Field()