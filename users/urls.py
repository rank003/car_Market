from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('inbox/', views.inbox_view, name='inbox'),
    path(
        'profile/<uuid:profile_id>/',
        views.profile_view,
        name='profile_detail',
    ),
    path('profile/edit/', views.update_profile, name='update-profile'),
    path('profile/delete/', views.delete_profile, name='delete-profile'),
]
