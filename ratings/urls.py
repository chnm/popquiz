from django.urls import path
from .views import rate_view, rate_api, save_review

urlpatterns = [
    path('rate/', rate_view, name='rate'),
    path('api/rate/', rate_api, name='rate_api'),
    path('api/review/', save_review, name='save_review'),
]
