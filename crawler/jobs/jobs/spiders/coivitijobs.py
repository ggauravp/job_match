import scrapy
from ..items import JobItem

class JobspiderSpider(scrapy.Spider):
    name = "jobspider"
    allowed_domains = ["globalcareers-cotiviti.icims.com"]
    start_urls = [
        "https://globalcareers-cotiviti.icims.com/jobs/search?ss=1&hashed=-625942729&in_iframe=1"
    ]

    def parse(self, response):
        # 1. Locate all job rows on the search page
        jobs = response.xpath("//div[contains(@class,'iCIMS_JobsTable')]//div[contains(@class,'row')]")

        for job in jobs:
            item = JobItem()

            full_title = job.xpath(".//div[contains(@class,'title')]/a/@title").get(default="").strip()
            title = full_title.split(" - ", 1)[-1] # Get text after the first " - "
            item["title"] = title
            # Get the link to the individual job page
            link = job.xpath(".//div[contains(@class,'title')]/a/@href").get()
            item["link"] = response.urljoin(link)

            item["location"] = job.xpath(
                ".//div[contains(@class,'left')]/span[not(contains(@class,'sr-only'))]/text()"
            ).get(default="").strip()

            item["deadline"] = None
            item["adzuna_id"] = None
            item["country"] = None
            item["company"] = "Cotiviti"

            # 2. "Follow" the link to the detail page to get the description
            # We pass the 'item' we already started filling into the next function via 'meta'
            if link:
                yield response.follow(item["link"], callback=self.parse_job_details, meta={'item': item})

    def parse_job_details(self, response):
        item = response.meta['item']

        # Responsibilities
        responsibilities = response.xpath(
            "//h2[contains(normalize-space(),'Responsibilities')]"
            "/following-sibling::div[1]"
            "//div[contains(@class,'iCIMS_Expandable_Container')]//text()"
        ).getall()

        # Qualifications
        qualifications = response.xpath(
            "//h2[contains(normalize-space(),'Qualifications')]"
            "/following-sibling::div[1]"
            "//div[contains(@class,'iCIMS_Expandable_Container')]//text()"
        ).getall()

        item["description"] = " ".join(
            [t.strip() for t in responsibilities if t.strip()]
        )

        item["qualifications"] = " ".join(
            [t.strip() for t in qualifications if t.strip()]
        )

        yield item