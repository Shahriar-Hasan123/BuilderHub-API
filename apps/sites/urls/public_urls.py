from django.urls import path

from apps.sites.views.public_views import PublishedPageView


urlpatterns = [
    path(
        "published/<slug:site_slug>/",
        PublishedPageView.as_view(),
        name="published-site-home",
    ),
    path(
        "published/<slug:site_slug>/<slug:page_slug>/",
        PublishedPageView.as_view(),
        name="published-site-page",
    ),
]
