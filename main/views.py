from django.shortcuts import render
from django.http import HttpResponse
from .forms import SignupForm
from django.shortcuts import redirect
from .models import Job, JobResume
from django.contrib import messages
from django.contrib.auth import logout
import PyPDF2
import io

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

from django.shortcuts import render
from django.contrib import messages
from .models import Job, JobResume
import PyPDF2

from django.shortcuts import render
from django.contrib import messages
from .models import Job, JobResume
import PyPDF2

from django.shortcuts import render
from django.contrib import messages
from .models import Job, JobResume
import PyPDF2

def jobs(request):
    jobs_queryset = Job.objects.all().order_by('-id')
    
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
                    
                    # Save or update resume
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
        else:
            messages.error(request, 'You must be logged in to upload a resume.')
    
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