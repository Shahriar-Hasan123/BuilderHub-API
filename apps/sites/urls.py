from django.urls import path

from .views import SiteDetailAPIView, SiteListCreateAPIView, SiteLockAPIView

urlpatterns = [
    path("sites/", SiteListCreateAPIView.as_view(), name="site-list-create"),
    path("sites/<int:pk>/", SiteDetailAPIView.as_view(), name="site-detail"),
    path('sites/<int:pk>/lock/', SiteLockAPIView.as_view(), name='site-lock-status'),
]
