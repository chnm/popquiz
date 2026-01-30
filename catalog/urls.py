from django.urls import path
from .views import HomeView, CategoryDetailView, AddItemView, SwipeVoteView, StatsView, DecadeStatsView, EclecticView, TasteMapView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('category/<slug:slug>/', CategoryDetailView.as_view(), name='category_detail'),
    path('category/<slug:slug>/add/', AddItemView.as_view(), name='add_item'),
    path('category/<slug:slug>/vote/', SwipeVoteView.as_view(), name='swipe_vote'),
    path('category/<slug:slug>/stats/', StatsView.as_view(), name='stats'),
    path('category/<slug:slug>/decades/', DecadeStatsView.as_view(), name='decades'),
    path('category/<slug:slug>/eclectic/', EclecticView.as_view(), name='eclectic'),
    path('category/<slug:slug>/taste-map/', TasteMapView.as_view(), name='taste_map'),
]
