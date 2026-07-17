from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import CustomUser
# Create your views here.

def register(request):
    if request.method == 'POST':
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip()
        password     = request.POST.get('password', '')
        password2    = request.POST.get('password2', '')
        phone_number = request.POST.get('phone_number', '').strip()
        plate_number = request.POST.get('plate_number', '').strip()

        def fail(msg):
            return render(request, 'accounts/register.html', {
                'error': msg,
                'form': request.POST,
            })

        if not first_name:
            return fail('First name is required.')
        if not last_name:
            return fail('Last name is required.')
        if not phone_number:
            return fail('Phone number is required.')
        if CustomUser.objects.filter(phone_number=phone_number).first() is not None:
            return fail('An account with that phone number already exists.')
        if not email:
            return fail('Email is required.')
        if CustomUser.objects.filter(email=email).first() is not None:
            return fail('An account with that email already exists.')
        if len(password) < 8:
            return fail('Password must be at least 8 characters.')
        if password != password2:
            return fail('Passwords do not match.')

        # Use cleaned phone number as the internal username (must be unique)
        username = ''.join(c for c in phone_number if c.isalnum() or c in '@.+-_')[:150]
        user = CustomUser.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            phone_number=phone_number,
            plate_number=plate_number or None,
        )
        login(request, user)
        return redirect('/parking/dashboard/')
    return render(request, 'accounts/register.html')

def user_login(request):
    if request.user.is_authenticated:
        return redirect('/parking/search/')
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        password     = request.POST.get('password', '')
        user_obj = CustomUser.objects.filter(phone_number=phone_number).first()
        user = authenticate(request, username=user_obj.username, password=password) if user_obj else None
        if user:
            login(request, user)
            next_url = request.GET.get('next', '/parking/dashboard/')
            return redirect(next_url)
        return render(request, 'accounts/login.html', {'error': 'Invalid phone number or password.'})
    return render(request, 'accounts/login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('home')