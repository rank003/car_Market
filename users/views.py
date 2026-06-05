from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages

from .models import Profile, Notification
from .forms import LoginForm, ProfileForm, RegisterForm


def register_user(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['name']
        username = form.cleaned_data['username']
        email = form.cleaned_data['email']
        password = form.cleaned_data['password1']

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name,
        )

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.username = user.username
        profile.email = user.email
        profile.name = name
        profile.save()

        authenticated_user = authenticate(
            request,
            username=username,
            password=password,
        )
        if authenticated_user is not None:
            login(request, authenticated_user)
        else:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(
            request,
            'Registration successful. Welcome to CarMarket!',
        )
        return redirect('home')

    return render(request, 'users/register.html', {'form': form})


def login_user(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful.')
            return redirect('home')
        messages.error(request, 'Invalid username or password')

    return render(request, 'users/login.html', {'form': form})


@login_required(login_url='login')
def logout_user(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required(login_url='login')
def profile_view(request, profile_id=None):
    if profile_id:
        profile = get_object_or_404(Profile, id=profile_id)
    else:
        profile, _ = Profile.objects.get_or_create(
            user=request.user,
            defaults={
                'username': request.user.username,
                'email': request.user.email,
                'name': request.user.get_full_name(),
            },
        )
    return render(request, 'users/profile.html', {'profile': profile})


@login_required(login_url='login')
def update_profile(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'username': request.user.username,
            'email': request.user.email,
            'name': request.user.get_full_name(),
        },
    )

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            updated_profile = form.save(commit=False)
            updated_profile.user = request.user
            updated_profile.username = request.user.username
            updated_profile.save()

            request.user.email = updated_profile.email
            request.user.first_name = updated_profile.name
            request.user.save(update_fields=['email', 'first_name'])

            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'users/edit-profile.html', {'form': form})


@login_required(login_url='login')
def delete_profile(request):
    if request.method != 'POST':
        return redirect('profile')

    profile = Profile.objects.filter(user=request.user).first()
    user = request.user

    logout(request)

    if profile:
        profile.delete()
    user.delete()

    messages.success(request, 'Your account and profile have been deleted.')
    return redirect('home')


@login_required(login_url='login')
def inbox_view(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'username': request.user.username,
            'email': request.user.email,
            'name': request.user.get_full_name(),
        },
    )

    notifications = profile.notifications.all()
    unread_count = notifications.filter(is_read=False).count()

    if request.method == 'POST':
        profile.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All inbox messages marked as read.')
        return redirect('inbox')

    return render(
        request,
        'users/inbox.html',
        {
            'profile': profile,
            'notifications': notifications,
            'unread_count': unread_count,
        },
    )
