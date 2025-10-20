# jobspider/pipelines.py
import psycopg2
from datetime import datetime

class PostgresJobPipeline:
    def open_spider(self, spider):
        self.conn = psycopg2.connect(
            dbname="job_recommendation",
            user="postgres",
            password="2003",
            host="localhost",
            port="5432"
        )
        self.cursor = self.conn.cursor()

    def close_spider(self, spider):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def process_item(self, item, spider):
        deadline_str = item.get('deadline')
        if deadline_str:
            try:
                deadline_date = datetime.strptime(deadline_str, "%b %d, %Y").date()
            except ValueError:
                deadline_date = None
        else:
            deadline_date = None

        today = datetime.today().date()
        if deadline_date and today > deadline_date:
            spider.logger.info(f"Skipping expired job: {item.get('job_title')}")
            return item

        # Savepoint per item to prevent transaction abort
        self.cursor.execute("SAVEPOINT sp_item")
        try:
            self.cursor.execute("""
                INSERT INTO main_job (title, company, location, url, description, country, adzuna_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    description = EXCLUDED.description,
                    country = EXCLUDED.country,
                    adzuna_id = EXCLUDED.adzuna_id
            """, (
                item.get('job_title'),
                item.get('company'),
                item.get('location'),
                item.get('cta_link'),
                item.get('description', ''),
                item.get('country', ''),
                None
            ))
            self.cursor.execute("RELEASE SAVEPOINT sp_item")
            self.conn.commit()
            spider.logger.info(f"Upserted job: {item.get('job_title')} at {item.get('company')}")
        except Exception as e:
            spider.logger.error(f"DB error for url={item.get('cta_link')}: {e}")
            self.cursor.execute("ROLLBACK TO SAVEPOINT sp_item")
            self.cursor.execute("RELEASE SAVEPOINT sp_item")

        return item
