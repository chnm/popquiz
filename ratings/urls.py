from django.urls import path
from .views import rate_view, rate_api

urlpatterns = [
    path('rate/', rate_view, name='rate'),
    path('api/rate/', rate_api, name='rate_api'),
]
