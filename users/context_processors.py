from .models import Profile, Notification


def inbox_unread_count(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"inbox_unread_count": 0}

    profile = Profile.objects.filter(user=request.user).first()
    if not profile:
        return {"inbox_unread_count": 0}

    unread_count = Notification.objects.filter(
        profile=profile,
        is_read=False,
    ).count()
    return {"inbox_unread_count": unread_count}
