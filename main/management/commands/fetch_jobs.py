from django.core.management.base import BaseCommand
from main.models import Job
import requests

# TECH JOB FILTERING LOGIC
TECH_KEYWORDS = [
    "software", "developer", "engineer", "backend", "frontend", "full stack",
    "python", "java", "javascript", "typescript", "react", "node",
    "machine learning", "ml", "ai", "data", "cloud", "aws", "devops",
    "mobile", "android", "ios", "flutter", "kotlin", "php",
    "c++", "c#", "ruby", "rails", "django", "flask", "html", "css",
    "sql", "database", "docker", "kubernetes", "cybersecurity", "blockchain",
    "network", "infrastructure", "qa", "testing", "automation",
    "technical support", "it support", "systems administrator", "it administrator",
    "scrum", "agile", "product manager", "project manager", "ux", "ui",
    "information technology", "it", "it specialist", "it technician",
    "data scientist", "data analyst", "big data", "hadoop", "spark",
    "artificial intelligence", "computer vision", "natural language processing", "nlp",
]

NON_TECH_KEYWORDS = [
    "cook", "chef", "plumber", "driver", "helper",
    "waiter", "cleaner", "housekeeping", "security", "labour", "labourer",
    "maintenance", "mechanic", "accounts", "sales", "transport", "manager", "clerk", "plasterer",
    "nurse", "teacher", "tutor", "receptionist", "cashier",
    "barber", "hairdresser", "beauty", "salon", "gardener",
    "electrician", "construction", "delivery",
    "retail", "warehouse", "factory", "assembly",
    "room attendant", "bellhop", "valet",
    "caregiver", "childcare", "counselor", "counsellor",
    "therapist", "social worker", "pharmacist", "paramedic", "veterinarian",
    "artist", "musician", "photographer", "designer", "journalist", "writer",
    "translator", "interpreter", "librarian", "archivist", "historian",
    "farmer", "agriculture", "fisherman", "pilot", "flight attendant",
    "airline", "bus driver", "taxi", "chauffeur", "train operator", "railway",
    "conductor", "postal worker", "firefighter", "emergency responder",
    "judge", "lawyer", "attorney", "paralegal", "legal assistant",
    "assistant", "business development", "hr", "human resources", "recruiter",
    "coach", "trainer", "fitness", "personal trainer", "gym instructor",
    "psychologist", "psychiatrist", "dietitian", "nutritionist", "culinary",
]

# JOB FILTER FUNCTION
def is_tech_job(title, description):
    text = (title + " " + description).lower()
    if any(word in text for word in NON_TECH_KEYWORDS):
        return False
    return any(word in text for word in TECH_KEYWORDS)


# COMMAND
class Command(BaseCommand):
    help = "Fetches jobs from Adzuna API and syncs database (add new, delete outdated)"

    # Adzuna credentials
    APP_ID = "5e3112e5"
    APP_KEY = "4554919ced83dc45c8bb8285f60ea2c6"
    COUNTRIES = ["in", "us", "gb", "ca", "au", "de", "fr", "nl","nz"]
    RESULTS_PER_PAGE = 20
    MAX_PAGES = 2  # safe limit

    def fetch_jobs_from_adzuna(self, description=""):
        all_jobs = []

        for country in self.COUNTRIES:
            for page in range(1, self.MAX_PAGES + 1):
                url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
                params = {
                    "app_id": self.APP_ID,
                    "app_key": self.APP_KEY,
                    "results_per_page": self.RESULTS_PER_PAGE,
                    "what": description,
                }

                response = requests.get(url, params=params)
                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f"Failed to fetch jobs from {country}, page {page}"))
                    continue

                data = response.json()
                jobs = data.get("results", [])
                if not jobs:
                    break

                self.stdout.write(self.style.SUCCESS(f"Fetched {len(jobs)} jobs from {country}, page {page}"))
                all_jobs.extend(jobs)

        return all_jobs

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting job sync with Adzuna API..."))

        try:
            api_jobs = self.fetch_jobs_from_adzuna(description="software developer engineer python java")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch jobs: {e}"))
            return

        if not api_jobs:
            self.stdout.write(self.style.WARNING("No jobs fetched from API."))
            return

        # Step 1.5: FILTER ONLY TECH JOBS
        tech_jobs = [job for job in api_jobs if is_tech_job(job.get("title", ""), job.get("description", ""))]
        self.stdout.write(self.style.SUCCESS(f"Tech jobs after filtering: {len(tech_jobs)}"))

        # Step 2: get all adzuna_ids from filtered tech jobs
        api_job_ids = set(job.get("id") for job in tech_jobs)

        # Step 3: delete jobs that are no longer in API
        deleted_count, _ = Job.objects.exclude(adzuna_id__in=api_job_ids).delete()
        self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} outdated jobs."))

        # Step 4: add new jobs
        existing_job_ids = set(Job.objects.values_list("adzuna_id", flat=True))
        new_jobs = []

        for job_data in tech_jobs:
            adzuna_id = job_data.get("id")
            if not adzuna_id or adzuna_id in existing_job_ids:
                continue

            job = Job(
                adzuna_id=adzuna_id,
                title=job_data.get("title", "N/A"),
                company=job_data.get("company", {}).get("display_name", "N/A"),
                location=job_data.get("location", {}).get("display_name", "N/A"),
                url=job_data.get("redirect_url", ""),
                description=job_data.get("description", ""),
                country=job_data.get("country_code") or job_data.get("location", {}).get("area", ["Unknown"])[-1],
            )
            new_jobs.append(job)

        if new_jobs:
            Job.objects.bulk_create(new_jobs)
            self.stdout.write(self.style.SUCCESS(f"Added {len(new_jobs)} new tech jobs."))
        else:
            self.stdout.write(self.style.SUCCESS("No new tech jobs to add."))

        self.stdout.write(self.style.SUCCESS("Tech Job sync completed!"))
