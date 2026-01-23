import psycopg2
from scrapy.exceptions import DropItem

class JobPipeline:
    def open_spider(self, spider):
        # Connect to PostgreSQL
        self.conn = psycopg2.connect(
            host="localhost",
            dbname="job_recommendation",
            user="postgres",
            password="2003"
        )
        self.cursor = self.conn.cursor()

    def close_spider(self, spider):
        self.cursor.close()
        self.conn.close()

    def clean_text(self, text):
        """Clean unwanted characters from text"""
        if text:
            return text.replace('\xa0', ' ').replace('\r', ' ').replace('\t', ' ').strip()
        return text

    def process_item(self, item, spider):
        # Clean fields
        item["title"] = self.clean_text(item.get("title"))
        item["company"] = self.clean_text(item.get("company"))
        item["location"] = self.clean_text(item.get("location"))
        item["description"] = self.clean_text(item.get("description"))
        item["country"] = self.clean_text(item.get("country"))
        item["deadline"] = self.clean_text(item.get("deadline"))


        # Insert into PostgreSQL
        try:
            self.cursor.execute("""
                INSERT INTO main_job (title, company, location, url, description, country, deadline, adzuna_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """, (
                item["title"],
                item["company"],
                item["location"],
                item["link"],
                item["description"],
                item["country"],
                item["deadline"],
                item["adzuna_id"],
            ))
            self.conn.commit()
        except Exception as e:
            spider.logger.error(f"Error inserting item '{item.get('title')}': {e}")
            self.conn.rollback()  # Rollback to prevent blocking next inserts

        return item