from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from jobs.spiders.coivitijobs import JobspiderSpider
from jobs.spiders.f1jobs import PagespiderSpider

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())

    # Add spiders to the process
    process.crawl(JobspiderSpider)
    process.crawl(PagespiderSpider)

    # Start the crawling process
    process.start()