from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .forms import SignupForm
from django.shortcuts import redirect
from .models import Job, JobResume, JobRating
from django.contrib import messages
from django.contrib.auth import logout
import PyPDF2
import io
from django.db.models import Q
from django.db.models import Avg, Count, FloatField, ExpressionWrapper, F

def home_page(request):
    return render(request, 'core/home.html', {'current_page': 'home'})

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


def jobs(request):
    jobs_queryset = Job.objects.all()

    # Search functionality
    query = request.GET.get('q')
    if query:
        jobs_queryset = jobs_queryset.filter(
            Q(title__icontains=query) 
        )

    jobs_queryset = jobs_queryset.order_by('?')[:20]

    # Attach user rating if logged in
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

    return render(request, 'core/jobs.html', {
        'jobs': jobs_queryset,
        'current_page': 'jobs'
    })


def custom_logout(request):
    """
    Custom logout view that redirects to jobs page
    """
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('main:home')

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

def top_jobs(request):
    # Annotate jobs with avg rating and number of ratings
    jobs = Job.objects.annotate(
        avg_rating=Avg('ratings__stars'),
        total_ratings=Count('ratings')
    ).filter(total_ratings__gt=2)  # Only consider jobs with more than 3 ratings

    # Global average rating across all jobs
    C = JobRating.objects.aggregate(avg=Avg('stars'))['avg'] or 0

    # Minimum ratings to be considered
    m = 3

    # Calculate weighted score for each job
    for job in jobs:
        R = job.avg_rating or 0
        v = job.total_ratings or 0
        job.weighted_score = (v/(v+m)) * R + (m/(v+m)) * C

    # Order by weighted_score descending
    jobs = sorted(jobs, key=lambda x: x.weighted_score, reverse=True)

    return render(request, 'core/top_jobs.html', {
        'jobs': jobs,
        'current_page': 'top_jobs'
    })

