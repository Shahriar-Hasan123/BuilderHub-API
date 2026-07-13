from django.urls import path
from .views import SiteListCreateAPIView, SiteDetailAPIView

urlpatterns = [
    path('sites/', SiteListCreateAPIView.as_view(), name='site-list-create'),
    path('sites/<int:pk>/', SiteDetailAPIView.as_view(), name='site-detail'),
]