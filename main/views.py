from django.shortcuts import render, redirect
from django.http import JsonResponse
from .forms import SignupForm
from .models import Job, JobResume, JobRating
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Q, Avg, Count
import PyPDF2
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
model = SentenceTransformer('all-MiniLM-L6-v2')
from sklearn.preprocessing import MinMaxScaler


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


#  RESUME SECTION EXTRACTION 
def detect_resume_sections_fixed(text):
    sections = {
        "profile": "",
        "skills": "",
        "projects": "",
        "experience": ""
    }
    current = "other"
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    headings = {
        "profile": ["PROFILE", "SUMMARY", "ABOUT"],
        "skills": ["SKILLS", "TECHNICAL SKILLS"],
        "projects": ["PROJECTS"],
        "experience": ["EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE"]
    }
    for line in lines:
        l_clean = line.upper()
        found = False
        for section, keys in headings.items():
            if l_clean in keys:
                current = section
                found = True
                break
        if not found:
            if current in sections:
                sections[current] += " " + line
    return {k: v.strip() for k, v in sections.items()}


#  JOB DESC SPLIT 
def split_job_text(text):
    desc = ""
    qual = ""

    d = re.search(r"(responsibilities|description)(.*?)(requirements|qualifications)", text, re.DOTALL)
    q = re.search(r"(requirements|qualifications)(.*)", text, re.DOTALL)

    if d:
        desc = d.group(2)
    if q:
        qual = q.group(2)

    return desc, qual


#  VALID JOB CHECK 
def is_valid_job(job):
    if not job.description or not getattr(job, 'qualifications', None):
        return False
    return True


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

    recommended_jobs = []
    resume_text = None

    if request.user.is_authenticated:
        existing_resume = JobResume.objects.filter(user=request.user).first()
        if existing_resume:
            resume_text = existing_resume.resume_text

    # RECOMMENDATION (EMBED PROFILE + TFIDF OTHERS) 
    if resume_text:
        try:
            cleaned_resume = clean_text(resume_text)
            resume_sections = detect_resume_sections_fixed(resume_text)
            cleaned_sections = {k: clean_text(v) for k, v in resume_sections.items()}

            # Profile embedding only
            profile_emb = model.encode(cleaned_sections["profile"])

            # TF-IDF vectorizers for skills, experience, projects
            tfidf_skills = TfidfVectorizer(ngram_range=(1,2), stop_words='english', sublinear_tf=True)
            tfidf_exp = TfidfVectorizer(ngram_range=(1,2), stop_words='english', sublinear_tf=True)
            tfidf_proj = TfidfVectorizer(ngram_range=(1,2), stop_words='english', sublinear_tf=True)

            # Prepare valid jobs
            valid_jobs = [job for job in Job.objects.all() if is_valid_job(job)]
            job_descs = [clean_text(split_job_text(job.description)[0]) for job in valid_jobs]
            job_quals = [clean_text(split_job_text(job.description)[1]) for job in valid_jobs]

            # TF-IDF matrices
            skills_matrix = tfidf_skills.fit_transform([cleaned_sections["skills"]] + job_quals)
            exp_matrix = tfidf_exp.fit_transform([cleaned_sections["experience"]] + job_quals)
            proj_matrix = tfidf_proj.fit_transform([cleaned_sections["projects"]] + job_descs)

            scores = []
            for idx, job in enumerate(valid_jobs):
                desc_emb = model.encode(job_descs[idx])
                qual_emb = model.encode(job_quals[idx])

                # Profile embedding similarity
                prof_desc_sim = cosine_similarity([profile_emb], [desc_emb])[0][0]
                prof_qual_sim = cosine_similarity([profile_emb], [qual_emb])[0][0]

                # TF-IDF similarities
                skill_qual_sim = cosine_similarity(skills_matrix[0:1], skills_matrix[idx+1:idx+2])[0][0]
                exp_qual_sim   = cosine_similarity(exp_matrix[0:1], exp_matrix[idx+1:idx+2])[0][0]
                proj_desc_sim  = cosine_similarity(proj_matrix[0:1], proj_matrix[idx+1:idx+2])[0][0]

                # Weighted final score
                final_score = (
                    0.10 * prof_desc_sim +
                    0.05 * prof_qual_sim +
                    0.25 * skill_qual_sim +
                    0.50 * exp_qual_sim +
                    0.10 * proj_desc_sim
                )

                job.similarity = final_score
                scores.append((final_score, job))

            # Scale scores 0-1
            scaler = MinMaxScaler()
            scaled = scaler.fit_transform([[s[0]] for s in scores])
            for i, (_, job) in enumerate(scores):
                job.similarity = scaled[i][0]

            # Sort top 8
            recommended_jobs = [job for _, job in sorted(scores, key=lambda x: x[0], reverse=True)[:8]]

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