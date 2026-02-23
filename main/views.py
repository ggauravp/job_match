from django.shortcuts import render, redirect
from django.http import JsonResponse
from .forms import SignupForm
from .models import Job, JobResume, JobRating
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Q, Avg, Count
import PyPDF2
import re
from .job_recommender import JobRecommender


#  HOME 
def home_page(request):
    return render(request, 'core/home.html', {'current_page': 'home'})


#  SIGNUP 
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


#  CLEAN FUNCTION 
# Note: recommendation processing lives in `main/job_recommender.py`.
# This views module only handles web endpoints and resume upload.


#  JOBS 
def jobs(request):

    jobs_queryset = Job.objects.all()
    query = request.GET.get('q')
    if query:
        jobs_queryset = jobs_queryset.filter(Q(title__icontains=query))
    jobs_queryset = jobs_queryset.order_by('?')[:20]

    for job in jobs_queryset:
        job.user_rating = None
        if request.user.is_authenticated:
            rating = JobRating.objects.filter(job=job, user=request.user).first()
            if rating:
                job.user_rating = rating.stars

    if request.user.is_authenticated and not request.session.get('welcome_shown'):
        messages.info(request, f'Welcome back, {request.user.username}! Upload your resume to get better job matches.')
        request.session['welcome_shown'] = True

        # Handle resume upload
    if request.method == 'POST' and 'resume' in request.FILES:
        if request.user.is_authenticated:
            resume_file = request.FILES['resume']
            if resume_file.name.endswith('.pdf'):
                try:
                    pdf_reader = PyPDF2.PdfReader(resume_file)
                    resume_text = ""
                    for page in pdf_reader.pages:
                        resume_text += page.extract_text() or ""

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

    recommended_jobs = []
    resume_text = None

    if request.user.is_authenticated:
        existing_resume = JobResume.objects.filter(user=request.user).first()
        if existing_resume:
            resume_text = existing_resume.resume_text

    # Use recommender that handles DB access itself (avoid duplicate reads/processing)
    if request.user.is_authenticated and existing_resume:
        try:
            recommender = JobRecommender()
            recs_df = recommender.recommend(request.user.id, top_n=8, min_score=0.4)

            # Map DataFrame rows back to Job model instances preserving order
            valid_jobs = list(Job.objects.all())
            id_to_job = {job.id: job for job in valid_jobs}
            recommended_jobs = []
            for _, row in recs_df.iterrows():
                jid = row.get('id')
                job_obj = id_to_job.get(jid)
                if job_obj:
                    job_obj.similarity = float(row.get('final_score', 0.0))
                    job_obj.skills_match = float(row.get('skills_match', 0.0))
                    job_obj.experience_match = float(row.get('experience_match', 0.0))
                    job_obj.profile_match = float(row.get('profile_match', 0.0))
                    job_obj.projects_match = float(row.get('projects_match', 0.0))
                    recommended_jobs.append(job_obj)

        except Exception as e:
            messages.error(request, f'Error generating recommendations: {str(e)}')

    return render(request, 'core/jobs.html', {
        'jobs': jobs_queryset,
        'recommended_jobs': recommended_jobs,
        'current_page': 'jobs'
    })


#  LOGOUT 
def custom_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('main:home')


#  RATE JOB 
def rate_job(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=403)

    job_id = request.POST.get('job_id')
    stars = request.POST.get('stars')

    try:
        job = Job.objects.get(id=int(job_id))
        stars = int(stars)
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)

    rating, created = JobRating.objects.update_or_create(
        job=job,
        user=request.user,
        defaults={'stars': stars}
    )

    return JsonResponse({'message': 'Rating saved', 'stars': rating.stars})


#  TOP JOBS 
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

def pdf_guide(request):
    return render(request, 'core/pdf_guide.html', {
        'current_page': 'pdf_guide'
    })