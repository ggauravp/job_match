from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from .forms import SignupForm
from .models import Job, JobResume, JobRating
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Q, Avg, Count
import PyPDF2
import re
import pandas as pd

# Recommendation imports
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load model once globally
model = SentenceTransformer('all-MiniLM-L6-v2')


# ================= HOME =================
def home_page(request):
    return render(request, 'core/home.html', {'current_page': 'home'})


# ================= SIGNUP =================
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully! Please log in to continue.')
            return redirect('main:login')
    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {
        'form': form,
        'current_page': 'signup'
    })


# ================= CLEAN FUNCTION =================
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\S+@\S+', ' ', text)
    text = re.sub(r'\+?\d[\d\s\-]{7,}', ' ', text)
    text = re.sub(r'http\S+', ' ', text)
    text = re.sub(r'[^a-z\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ================= JOBS =================
def jobs(request):
    jobs_queryset = Job.objects.all()

    # Search
    query = request.GET.get('q')
    if query:
        jobs_queryset = jobs_queryset.filter(Q(title__icontains=query))

    jobs_queryset = jobs_queryset.order_by('?')[:20]

    # Attach rating
    for job in jobs_queryset:
        job.user_rating = None
        if request.user.is_authenticated:
            rating = JobRating.objects.filter(job=job, user=request.user).first()
            if rating:
                job.user_rating = rating.stars

    # Welcome message
    if request.user.is_authenticated and not request.session.get('welcome_shown'):
        messages.info(request, f'Welcome back, {request.user.username}! Upload your resume to get better job matches.')
        request.session['welcome_shown'] = True

    recommended_jobs = []
    resume_text = None

    # ================= Resume Upload / Existing Resume =================
    if request.user.is_authenticated:
        # 1️⃣ Resume Upload
        if request.method == 'POST' and 'resume' in request.FILES:
            resume_file = request.FILES['resume']
            if resume_file.name.endswith('.pdf'):
                try:
                    pdf_reader = PyPDF2.PdfReader(resume_file)
                    resume_text = ""
                    for page in pdf_reader.pages:
                        resume_text += page.extract_text() or ""

                    # Save resume in DB
                    JobResume.objects.update_or_create(
                        user=request.user,
                        defaults={
                            'resume': resume_file,
                            'resume_text': resume_text
                        }
                    )
                    messages.success(request, 'Resume uploaded successfully!')

                except Exception as e:
                    messages.error(request, f'Error processing PDF: {str(e)}')
            else:
                messages.error(request, 'Please upload a valid PDF file.')

        # 2️⃣ If no upload, check for existing resume
        else:
            existing_resume = JobResume.objects.filter(user=request.user).first()
            if existing_resume:
                resume_text = existing_resume.resume_text

    # ================= Generate Recommendations =================
    if resume_text:
        try:
            cleaned_resume = clean_text(resume_text)

            jobs_data = []
            for job in Job.objects.all():
                jobs_data.append({
                    "id": job.id,
                    "title": job.title,
                    "company": getattr(job, "company", ""),
                    "location": job.location,
                    "country": getattr(job, "country", ""),
                    "url": getattr(job, "url", "#"),
                    "description": job.description,
                    "clean_desc": clean_text(job.description)
                })

            jobs_df = pd.DataFrame(jobs_data)
            jobs_df = jobs_df[jobs_df["clean_desc"] != ""]

            resume_embedding = model.encode([cleaned_resume])
            job_embeddings = model.encode(jobs_df["clean_desc"].tolist())

            similarity_scores = cosine_similarity(resume_embedding, job_embeddings)[0]
            jobs_df["similarity"] = similarity_scores

            # Top 8 recommended jobs
            recommended_jobs = jobs_df.sort_values(
                by="similarity",
                ascending=False
            ).head(8).to_dict(orient="records")

        except Exception as e:
            messages.error(request, f'Error generating recommendations: {str(e)}')

    return render(request, 'core/jobs.html', {
        'jobs': jobs_queryset,
        'recommended_jobs': recommended_jobs,
        'current_page': 'jobs'
    })


# ================= LOGOUT =================
def custom_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('main:home')


# ================= RATE JOB =================
def rate_job(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=403)

    job_id = request.POST.get('job_id')
    stars = request.POST.get('stars')

    if not job_id or not stars:
        return JsonResponse({'error': 'Invalid data'}, status=400)

    try:
        job = Job.objects.get(id=int(job_id))
        stars = int(stars)
    except (Job.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Invalid job or stars'}, status=400)

    rating, created = JobRating.objects.update_or_create(
        job=job,
        user=request.user,
        defaults={'stars': stars}
    )

    return JsonResponse({'message': 'Rating saved', 'stars': rating.stars})


# ================= TOP JOBS =================
def top_jobs(request):
    jobs = Job.objects.annotate(
        avg_rating=Avg('ratings__stars'),
        total_ratings=Count('ratings')
    ).filter(total_ratings__gt=2)

    C = JobRating.objects.aggregate(avg=Avg('stars'))['avg'] or 0
    m = 3

    for job in jobs:
        R = job.avg_rating or 0
        v = job.total_ratings or 0
        job.weighted_score = (v/(v+m)) * R + (m/(v+m)) * C

    jobs = sorted(jobs, key=lambda x: x.weighted_score, reverse=True)

    return render(request, 'core/top_jobs.html', {
        'jobs': jobs,
        'current_page': 'top_jobs'
    })