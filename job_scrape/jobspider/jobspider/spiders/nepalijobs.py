# jobspider/spiders/nepalijobs.py
import scrapy
from datetime import datetime

class NepalijobsSpider(scrapy.Spider):
    name = "nepalijobs"
    allowed_domains = ["career.f1soft.com"]
    start_urls = ["https://career.f1soft.com"]

    def parse(self, response):
        jobs = response.css("div.features-job")
        for job in jobs:
            company = job.css('a.fw-600.text-f1.small::text').get()
            job_title = job.css('h3 a::text').get()
            location = job.css('ul li span.small::text').get()
            cta_link = job.css('div.cta a::attr(href)').get()

            # Deadline may be inside <p class="days"> or absent
            deadline_text = job.css('p.days::text').get()
            if deadline_text:
                deadline_text = deadline_text.replace("Deadline:", "").strip()
            else:
                deadline_text = None

            # Description - optional, can scrape from job page if needed
            description = None

            self.logger.info(
                f"Job: {job_title} at {company} | {location} | {cta_link} | Deadline: {deadline_text}"
            )

            yield {
                "company": company,
                "job_title": job_title,
                "location": location,
                "cta_link": cta_link,
                "deadline": deadline_text,
                "description": description,
                "country": "Nepal",  # static
            }
