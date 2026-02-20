from core.celery import shared_task
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from crawler.jobs.jobs.spiders.coivitijobs import JobspiderSpider
from crawler.jobs.jobs.spiders.f1jobs import PagespiderSpider
from crawler.jobs.jobs.spiders.fusemachines import FusemachinesJobSpider

@shared_task
def run_all_crawlers():
    process = CrawlerProcess(get_project_settings())
    
    process.crawl(JobspiderSpider)
    process.crawl(PagespiderSpider)
    process.crawl(FusemachinesJobSpider)
    
    process.start()