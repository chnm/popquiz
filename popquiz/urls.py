from django.contrib import admin
from django.urls import path, include
from django.views.static import serve
from django.conf import settings

from accounts.views import ProfileView, CompareUsersView, CompareThreeUsersView, TeamView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),  # our custom views take priority over allauth
    path('accounts/', include('allauth.urls')),
    path('team/', TeamView.as_view(), name='team'),
    path('profile/<str:username>/', ProfileView.as_view(), name='profile'),
    path('compare/<str:username1>/<str:username2>/', CompareUsersView.as_view(), name='compare_users'),
    path('compare/<str:username1>/<str:username2>/<str:username3>/', CompareThreeUsersView.as_view(), name='compare_three_users'),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    path('', include('catalog.urls')),
    path('', include('ratings.urls')),
]
