from django.urls import path

from .views import SiteDetailAPIView, SiteListCreateAPIView, SiteLockAPIView, SitePublishAPIView

urlpatterns = [
    path("sites/", SiteListCreateAPIView.as_view(), name="site-list-create"),
    path("sites/<int:pk>/", SiteDetailAPIView.as_view(), name="site-detail"),
    path("sites/<int:pk>/lock/", SiteLockAPIView.as_view(), name="site-lock"),
    path('v1/sites/<int:pk>/publish/', SitePublishAPIView.as_view(), name='site-publish'),

]
