# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class JobItem(scrapy.Item):
    title = scrapy.Field()
    company = scrapy.Field()
    location = scrapy.Field()
    url = scrapy.Field()
    description = scrapy.Field()
    country = scrapy.Field()
    deadline = scrapy.Field()
    adzuna_id = scrapy.Field()  # None for crawled jobs
