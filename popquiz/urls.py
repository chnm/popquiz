from django.contrib import admin
from django.urls import path, include

from accounts.views import ProfileView, CompareUsersView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('profile/<str:username>/', ProfileView.as_view(), name='profile'),
    path('compare/<str:username1>/<str:username2>/', CompareUsersView.as_view(), name='compare_users'),
    path('', include('catalog.urls')),
    path('', include('votes.urls')),
]
