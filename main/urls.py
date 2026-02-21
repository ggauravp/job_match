from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import loginform

app_name = 'main'

urlpatterns = [
    path('', views.home_page, name='home'), 
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html', authentication_form=loginform, next_page='main:home'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('jobs/', views.jobs, name='jobs'),
    path('rate-job/', views.rate_job, name='rate_job'),
    path('top-jobs/', views.top_jobs, name='top_jobs'),
    path('pdf-guide/', views.pdf_guide, name='pdf_guide'),
    ]
