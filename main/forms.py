from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

class loginform(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Your username',
        'class': 'w-full py-4 px-6 rounded-xl'
        }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Your password',
        'class': 'w-full py-4 px-6 rounded-xl'
        }))
    

class SignupForm(UserCreationForm):
    # First Name
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'John',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))
    
    # Last Name
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Doe',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))
    
    # Username
    username = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Your username',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))
    
    # Email
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Your email address',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))
    
    # Passwords
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Your password',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Repeat password',
        'class': 'w-full py-4 px-6 rounded-xl bg-white/20 text-white placeholder-white/60 focus:ring-2 focus:ring-yellow-300 outline-none'
    }))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')
