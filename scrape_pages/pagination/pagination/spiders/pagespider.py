import scrapy
from ..items import JobItem

class PagespiderSpider(scrapy.Spider):
    name = "pagespider"
    allowed_domains = ["career.f1soft.com"]
    start_urls = ["https://career.f1soft.com/jobs?page=1"]

    def parse(self, response):
        jobs = response.css("div.features-job")

        for job in jobs:
            company = job.css('a.fw-600.text-f1.small::text').get()
            job_title = job.css('h3 a::text').get()
            location = job.css('ul li span.small::text').get()
            cta_link = job.css('div.cta a::attr(href)').get()
            deadline_text = job.css('p.days::text').get()

            if deadline_text:
                deadline_text = deadline_text.replace("Deadline:", "").strip()

            if cta_link:
                yield response.follow(
                    cta_link,
                    callback=self.parse_job_detail,
                    meta={
                        "company": company,
                        "job_title": job_title,
                        "location": location,
                        "deadline": deadline_text,
                    }
                )

        # Pagination
        page_links = response.css('li.page-item a.page-link::attr(href)').getall()
        for link in set(page_links):
            yield response.follow(link, callback=self.parse)

    def parse_job_detail(self, response):
        company = response.meta.get("company")
        job_title = response.meta.get("job_title")
        location = response.meta.get("location")
        deadline = response.meta.get("deadline")

        qualification = response.xpath(
            "//h3[contains(text(),'Qualification')]/following-sibling::ul[1]/li/text()"
        ).getall()

        job_description = response.xpath(
            "//h3[contains(text(),'Job Description')]/following-sibling::ul[1]/li/text()"
        ).getall()

        required_skills = response.xpath(
            "//h3[contains(text(),'Required Skills')]/following-sibling::ul[1]/li/text()"
        ).getall()

        description = "\n".join(job_description + qualification + required_skills)

        # Yield item to pipeline
        item = JobItem(
            title=job_title,
            company=company,
            location=location,
            url=response.url,
            description=description,
            country="Nepal",
            deadline=deadline,
            adzuna_id=None  # since crawled
        )
        yield item
