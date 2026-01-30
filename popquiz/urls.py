from django.contrib import admin
from django.urls import path, include

from accounts.views import ProfileView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('profile/<str:username>/', ProfileView.as_view(), name='profile'),
    path('', include('catalog.urls')),
    path('', include('votes.urls')),
]
