import scrapy
import json
from scrapy.selector import Selector

# Ensure your items.py is imported correctly
# from your_project_name.items import JobItem 

class FusemachinesJobSpider(scrapy.Spider):
    name = 'fuse_jobs'
    start_urls = ['https://api-website-v1.fusemachines.com/api/v1/careers?status=open&send_to_job_boards=Yes']

    def parse(self, response):
        jobs_list = json.loads(response.text)

        for job in jobs_list:
            html_content = job.get('description', '')
            sel = Selector(text=html_content)

            # Extracting the list items for Responsibilities and Qualifications
            # Using //li//text() to capture text inside nested <span> or <strong> tags
            resp_list = sel.xpath("//h3[contains(., 'Responsibilities')]/following-sibling::ul[1]/li//text()").getall()
            qual_list = sel.xpath("//h3[contains(., 'Qualifications')]/following-sibling::ul[1]/li//text()").getall()

            # Clean and join the lists into strings
            clean_resp = " ".join([r.strip() for r in resp_list if r.strip()])
            clean_qual = " ".join([q.strip() for q in qual_list if q.strip()])

            # Mapping to your JobItem structure
            city = job.get('city')
            country = job.get('country_id')

            location = ", ".join([x for x in [city, country] if x])
            board_code = job.get("board_code")
            link = None
            if board_code:
                link = f"https://fusemachines.applytojob.com/apply/{board_code}"

            yield {
                'title': job.get('title'),
                'company': 'Fusemachines',
                'location': location,
                'link': link,
                'description': clean_resp,
                'qualifications': clean_qual,
                'country': country,
                'deadline': None,
                'adzuna_id': None
            }