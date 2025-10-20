import requests
from requests.exceptions import RequestException
from main.models import Job  

def get_jobs(description="", location="", app_id= "5e3112e5", app_key="cdaaa336bf61d3926d77f5dc31ddfc0c"):
    """
    Fetches job listings from the Adzuna API across multiple countries.
    Requires app_id and app_key to be passed in.
    """
    # Ensure API keys are provided
    if not app_id or not app_key:
        print("Error: Adzuna App ID and App Key are required.")
        return []

    countries = ["in", "us", "gb", "ca", "au"]  # India, USA, UK, Canada, Australia
    all_jobs = []

    for country in countries:
        # Corrected parameter names: 'what' and 'where'
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": description,
            "where": location,
            "results_per_page": 20 # You can make this a parameter too
        }
        
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        
        try:
            # Added a try...except block for network errors
            response = requests.get(url, params=params)
            
            # This will raise an exception for HTTP error codes (4xx or 5xx)
            response.raise_for_status() 
            
            jobs = response.json().get("results", [])
            print(f"Fetched {len(jobs)} jobs from {country.upper()}")
            all_jobs.extend(jobs)

        except RequestException as e:
            # Catches connection errors, timeouts, etc.
            print(f"Failed to fetch jobs from {country.upper()}. Error: {e}")
        
    return all_jobs


def save_jobs_to_db(description="", location=""):
    jobs = get_jobs(description, location)
    print(f"Saving {len(jobs)} jobs to database...")

    for job in jobs:
        Job.objects.get_or_create(
            title=job.get("title", "N/A"),
            company=job.get("company", {}).get("display_name", "N/A"),
            location=job.get("location", {}).get("display_name", "N/A"),
            url=job.get("redirect_url", ""),
            description=job.get("description", ""),
            country=job.get("location", {}).get("area", ["N/A"])[0],
        )
    print("✅ Job data saved successfully!")
