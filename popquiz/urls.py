from django.contrib import admin
from django.urls import path, include

from accounts.views import ProfileView, CompareUsersView, CompareThreeUsersView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # django-allauth URLs (must come before accounts.urls)
    path('accounts/', include('accounts.urls')),
    path('profile/<str:username>/', ProfileView.as_view(), name='profile'),
    path('compare/<str:username1>/<str:username2>/', CompareUsersView.as_view(), name='compare_users'),
    path('compare/<str:username1>/<str:username2>/<str:username3>/', CompareThreeUsersView.as_view(), name='compare_three_users'),
    path('', include('catalog.urls')),
    path('', include('ratings.urls')),
]
