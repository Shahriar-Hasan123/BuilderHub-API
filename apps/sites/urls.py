from django.urls import path

from .views import SiteDetailAPIView, SiteListCreateAPIView, SiteLockRefreshApiView, SiteLockReleaseAPIView

urlpatterns = [
    path("sites/", SiteListCreateAPIView.as_view(), name="site-list-create"),
    path("sites/<int:pk>/", SiteDetailAPIView.as_view(), name="site-detail"),
    path("sites/<int:pk>/lock/refresh", SiteLockRefreshApiView.as_view(), name="site-lock-refresh"),
    path('sites/<int:pk>/lock/release/', SiteLockReleaseAPIView.as_view(), name='site-lock-release'),

]
