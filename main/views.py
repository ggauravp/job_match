from django.shortcuts import render
from django.http import HttpResponse
from .forms import SignupForm
from django.shortcuts import redirect
from .models import Job

def home_page(request):
    return render(request, 'core/home.html')

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)

        if form.is_valid():
            form.save()

            return redirect('/login/')
    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {
        'form': form
    })

def jobs(request):
    jobs_queryset = Job.objects.all().order_by('-id')
    return render(request, 'core/jobs.html', {
        'jobs': jobs_queryset
    })