from django.urls import path
from django.views.generic import RedirectView
from .views import HomeView, CategoryDetailView, AddItemView, AddByDirectorView, AddByActorView, AddMusicSearchView, AddMusicView, SwipeRatingView, StatsView, DecadeStatsView, EclecticView, DivisiveView, ItemDetailView, AddSongView, VisualizationsView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('music/add/', AddMusicView.as_view(), name='add_music'),
    path('category/<slug:slug>/', CategoryDetailView.as_view(), name='category_detail'),
    path('category/<slug:slug>/add/', AddItemView.as_view(), name='add_item'),
    path('category/<slug:slug>/add-by-director/', AddByDirectorView.as_view(), name='add_by_director'),
    path('category/<slug:slug>/add-by-actor/', AddByActorView.as_view(), name='add_by_actor'),
    path('category/<slug:slug>/add-by-search/', AddMusicSearchView.as_view(), name='add_music_search'),
    path('category/<slug:slug>/rate/', SwipeRatingView.as_view(), name='swipe_rating'),
    path('category/<slug:slug>/stats/', StatsView.as_view(), name='stats'),
    path('category/<slug:slug>/decades/', DecadeStatsView.as_view(), name='decades'),
    path('category/<slug:slug>/eclectic/', EclecticView.as_view(), name='eclectic'),
    path('category/<slug:slug>/divisive/', DivisiveView.as_view(), name='divisive'),
    path('category/<slug:category_slug>/item/<int:item_id>/', ItemDetailView.as_view(), name='item_detail'),
    path('category/<slug:category_slug>/item/<int:item_id>/add-song/', AddSongView.as_view(), name='add_song'),
    path('category/<slug:category_slug>/movie/<int:item_id>/', RedirectView.as_view(pattern_name='item_detail', permanent=True)),
    path('visualizations/', VisualizationsView.as_view(), name='visualizations'),
]
