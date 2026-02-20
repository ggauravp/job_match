import scrapy
from ..items import JobItem

class PagespiderSpider(scrapy.Spider):
    name = "pagespider"
    allowed_domains = ["career.f1soft.com"]
    start_urls = ["https://career.f1soft.com/jobs?page=1"]

    def parse(self, response):
        # 1. Select all job containers using the partial class match
        job_containers = response.xpath("//div[contains(@class, 'features-job')]")

        for job in job_containers:
            item = JobItem()

            # Extract list-level data
            item["company"] = job.xpath(".//div[contains(@class, 'box-content')]/a/text()").get(default="").strip()
            item["title"] = job.xpath(".//h3[contains(@class, 'fs-6')]/a/text()").get(default="").strip()
            item["location"] = job.xpath(".//div[@class='location-div']//span[@class='small']/text()").get(default="").strip()
            
            job_link = job.xpath(".//h3/a/@href").get()
            item["link"] = response.urljoin(job_link)
            
            # Default values for fields not on the list page
            item["country"] = "Nepal"
            item["adzuna_id"] = None

            if job_link:
                # IMPORTANT: Ensure callback name matches the function name below
                yield response.follow(item["link"], callback=self.parse_job_details, meta={'item': item})

            page_links = response.css('li.page-item a.page-link::attr(href)').getall()
            for link in set(page_links):
                yield response.follow(link, callback=self.parse)

    def parse_job_details(self, response):
        item = response.meta['item']

        # Extract Deadline
        deadline_text = response.xpath("//div[@class='deadline-div']//span[@class='small']/text()").get(default="")
        item["deadline"] = deadline_text.replace("Application Deadline:", "").strip()

        # Extract Job Description
        job_description = response.xpath(
            "//h3[contains(text(),'Job Description')]/following-sibling::ul[1]/li//text()"
        ).getall()
        item["description"] = "\n".join([t.strip() for t in job_description if t.strip()])

        # Extract Qualification + Required Skills
        qualification = response.xpath(
            "//h3[contains(text(),'Qualification')]/following-sibling::ul[1]/li//text()"
        ).getall()
        required_skills = response.xpath(
            "//h3[contains(text(),'Required Skills')]/following-sibling::ul[1]/li//text()"
        ).getall()
        combined_qualifications = qualification + required_skills
        item["qualifications"] = "\n".join([t.strip() for t in combined_qualifications if t.strip()])

        yield item