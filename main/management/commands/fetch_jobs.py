from django.core.management.base import BaseCommand
from main.models import Job
from main.utils import get_jobs


class Command(BaseCommand):
    help = "Fetches jobs from Adzuna API and syncs database (add new, delete outdated)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting job sync with Adzuna API..."))

        # Step 1: fetch jobs from API
        try:
            api_jobs = get_jobs(description=" ")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch jobs: {e}"))
            return

        if not api_jobs:
            self.stdout.write(self.style.WARNING("No jobs fetched from API."))
            return

        # Step 2: get all adzuna_ids from API
        api_job_ids = set(job.get("id") for job in api_jobs)

        # Step 3: delete jobs that are no longer in API
        deleted_count, _ = Job.objects.exclude(adzuna_id__in=api_job_ids).delete()
        self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} outdated jobs."))

        # Step 4: add new jobs
        existing_job_ids = set(Job.objects.values_list("adzuna_id", flat=True))
        new_jobs = []

        for job_data in api_jobs:
            adzuna_id = job_data.get("id")
            if not adzuna_id:
                continue  # skip if API returns job without ID

            if adzuna_id not in existing_job_ids:
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
            self.stdout.write(self.style.SUCCESS(f"Added {len(new_jobs)} new jobs."))
        else:
            self.stdout.write(self.style.SUCCESS("No new jobs to add."))

        self.stdout.write(self.style.SUCCESS("Job sync completed!"))
