from django.urls import path
from .views import (
    RegisterView, CustomLoginView, CustomLogoutView,
    MagicLinkRequestView, MagicLinkVerifyView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('magic-link/', MagicLinkRequestView.as_view(), name='magic_link_request'),
    path('magic-link/<str:token>/', MagicLinkVerifyView.as_view(), name='magic_link_verify'),
]
