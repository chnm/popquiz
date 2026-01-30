from django.urls import path
from .views import vote_view, vote_api

urlpatterns = [
    path('vote/', vote_view, name='vote'),
    path('api/vote/', vote_api, name='vote_api'),
]
