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
                    # Clear cached recommendations when resume is updated
                    if 'recommendations_cache' in request.session:
                        del request.session['recommendations_cache']
                    if 'resume_id_cache' in request.session:
                        del request.session['resume_id_cache']
                    request.session.modified = True
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

    # Use recommender with session-based caching to avoid recomputing on every page load
    if request.user.is_authenticated and existing_resume:
        try:
            # Check if recommendations are cached for this resume
            cached_recs = request.session.get('recommendations_cache', None)
            cached_resume_id = request.session.get('resume_id_cache', None)

            if cached_recs and cached_resume_id == existing_resume.id:
                # Use cached recommendations
                recommended_jobs_data = cached_recs
            else:
                # Compute fresh recommendations
                recommender = JobRecommender()
                recs_df = recommender.recommend(request.user.id, top_n=8, min_score=0.4)

                # Store recommendations in session cache
                recommended_jobs_data = []
                for _, row in recs_df.iterrows():
                    recommended_jobs_data.append({
                        'id': int(row.get('id', 0)),
                        'title': str(row.get('title', '')),
                        'company': str(row.get('company', '')),
                        'final_score': float(row.get('final_score', 0.0)),
                        'skills_match': float(row.get('skills_match', 0.0)),
                        'experience_match': float(row.get('experience_match', 0.0)),
                        'profile_match': float(row.get('profile_match', 0.0)),
                        'projects_match': float(row.get('projects_match', 0.0)),
                        'url': str(row.get('url', ''))
                    })

                request.session['recommendations_cache'] = recommended_jobs_data
                request.session['resume_id_cache'] = existing_resume.id
                request.session.modified = True

            # Map cached data back to Job model instances with scores
            rec_ids = [rec['id'] for rec in recommended_jobs_data]
            
            jobs_qs = Job.objects.filter(id__in=rec_ids)
            id_to_job = {job.id: job for job in jobs_qs}
            
            recommended_jobs = []
            for rec in recommended_jobs_data:
                job = id_to_job.get(rec['id'])
                if job:
                    job.similarity = rec['final_score']
                    job.skills_match = rec['skills_match']
                    job.experience_match = rec['experience_match']
                    job.profile_match = rec['profile_match']
                    job.projects_match = rec['projects_match']
                    recommended_jobs.append(job)

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