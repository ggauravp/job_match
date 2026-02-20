from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from jobs.spiders.coivitijobs import JobspiderSpider
from jobs.spiders.f1jobs import PagespiderSpider
from jobs.spiders.fusemachines import FusemachinesJobSpider

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())

    # Add spiders to the process
    process.crawl(JobspiderSpider)
    process.crawl(PagespiderSpider)
    process.crawl(FusemachinesJobSpider)

    # Start the crawling process
    process.start()