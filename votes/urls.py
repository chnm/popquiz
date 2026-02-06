from django.urls import path
from .views import vote_view, vote_api, song_upvote_api

urlpatterns = [
    path('vote/', vote_view, name='vote'),
    path('api/vote/', vote_api, name='vote_api'),
    path('api/song-upvote/', song_upvote_api, name='song_upvote_api'),
]
