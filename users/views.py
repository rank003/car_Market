import os
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.db.models import Q

from .models import Profile, Notification
from .forms import LoginForm, ProfileForm, RegisterForm


def _store_profile_image(uploaded_file):
    if not uploaded_file:
        return ""

    storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    base_name, ext = os.path.splitext(uploaded_file.name)
    safe_name = f"profiles/{uuid.uuid4().hex}_{base_name[:40]}{ext}"
    stored_name = storage.save(safe_name, uploaded_file)
    return f"{settings.MEDIA_URL}{stored_name}"


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

        return render(request, 'users/register.html', {
            'form': form,
            'register_success': True,
            'redirect_url': '/',
        })

    return render(request, 'users/register.html', {'form': form})


def login_user(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = LoginForm(request.POST or None)
    auth_error = None
    login_success = False

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            login_success = True
        else:
            auth_error = 'Invalid username or password. Please try again.'

    return render(request, 'users/login.html', {
        'form': form,
        'auth_error': auth_error,
        'login_success': login_success,
        'redirect_url': '/',
    })


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
def create_profile(request):
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'username': request.user.username,
            'email': request.user.email,
            'name': request.user.get_full_name(),
        },
    )

    if not created:
        messages.info(request, 'Your profile already exists. You can edit it instead.')
        return redirect('update-profile')

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            created_profile = form.save(commit=False)
            created_profile.user = request.user
            created_profile.username = request.user.username

            uploaded_profile_image = form.cleaned_data.get('profile_image')
            if uploaded_profile_image:
                created_profile.profile_image = _store_profile_image(uploaded_profile_image)

            created_profile.save()

            request.user.email = created_profile.email
            request.user.first_name = created_profile.name
            request.user.save(update_fields=['email', 'first_name'])

            messages.success(request, 'Profile created successfully.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'users/edit-profile.html', {
        'form': form,
        'page_title': 'Create Profile',
        'submit_label': 'Create Profile',
    })


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
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            updated_profile = form.save(commit=False)
            updated_profile.user = request.user
            updated_profile.username = request.user.username

            uploaded_profile_image = form.cleaned_data.get('profile_image')
            if uploaded_profile_image:
                updated_profile.profile_image = _store_profile_image(uploaded_profile_image)

            updated_profile.save()

            request.user.email = updated_profile.email
            request.user.first_name = updated_profile.name
            request.user.save(update_fields=['email', 'first_name'])

            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'users/edit-profile.html', {
        'form': form,
        'page_title': 'Edit Profile',
        'submit_label': 'Save Changes',
    })


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

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()
        notification_id = (request.POST.get('notification_id') or '').strip()
        notification = profile.notifications.filter(id=notification_id).first() if notification_id else None

        if action == 'mark_all_read':
            marked = profile.notifications.filter(is_read=False).update(is_read=True)
            if marked:
                messages.success(request, f'{marked} message(s) marked as read.')
            else:
                messages.info(request, 'All messages are already marked as read.')
            return redirect('inbox')

        if not notification:
            messages.error(request, 'Message not found.')
            return redirect('inbox')

        if action == 'mark_read':
            if notification.is_read:
                messages.info(request, 'Message is already marked as read.')
            else:
                notification.is_read = True
                notification.save(update_fields=['is_read'])
                messages.success(request, 'Message marked as read.')
            return redirect('inbox')

        if action == 'delete':
            notification.delete()
            messages.success(request, 'Message deleted.')
            return redirect('inbox')

        if action == 'reply':
            reply_text = (request.POST.get('reply_message') or '').strip()
            if not reply_text:
                messages.error(request, 'Reply cannot be empty.')
                return redirect(f"{request.path}?view={notification.id}")

            sender_name = profile.name or profile.username or request.user.username
            recipients = Profile.objects.filter(
                user__isnull=False,
            ).filter(
                Q(user__is_staff=True) | Q(user__is_superuser=True)
            ).exclude(id=profile.id)

            if not recipients.exists():
                messages.info(request, 'No admin recipients available for this reply.')
                return redirect('inbox')

            reply_subject = f"Reply from {sender_name}: {notification.subject}"
            for recipient in recipients:
                Notification.objects.create(
                    profile=recipient,
                    subject=reply_subject[:255],
                    message=reply_text,
                    is_read=False,
                )

            if not notification.is_read:
                notification.is_read = True
                notification.save(update_fields=['is_read'])

            messages.success(request, 'Reply sent successfully.')
            return redirect('inbox')

        messages.error(request, 'Unsupported inbox action.')
        return redirect('inbox')

    notifications = profile.notifications.all()
    unread_count = profile.notifications.filter(is_read=False).count()
    view_notification_id = (request.GET.get('view') or '').strip()

    return render(
        request,
        'users/inbox.html',
        {
            'profile': profile,
            'notifications': notifications,
            'unread_count': unread_count,
            'view_notification_id': view_notification_id,
        },
    )
