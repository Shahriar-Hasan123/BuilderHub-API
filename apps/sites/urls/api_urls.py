from django.urls import path

from ..views.api_views import (
    SiteDetailAPIView,
    SiteImageDetailAPIView,
    SiteImageListAPIView,
    SiteListCreateAPIView,
    SiteLockAPIView,
    SitePublishAPIView,
    SitePublishVersionDetailAPIView,
    SitePublishVersionListAPIView,
    SiteRollbackAPIView,
)

urlpatterns = [
    path("sites", SiteListCreateAPIView.as_view(), name="site-list-create"),
    path("sites/<int:pk>", SiteDetailAPIView.as_view(), name="site-detail"),
    path(
        "sites/<int:site_pk>/images",
        SiteImageListAPIView.as_view(),
        name="site-image-list",
    ),
    path(
        "sites/<int:site_pk>/images/<int:pk>",
        SiteImageDetailAPIView.as_view(),
        name="site-image-detail",
    ),
    path("sites/<int:pk>/lock", SiteLockAPIView.as_view(), name="site-lock"),
    path("sites/<int:pk>/publish", SitePublishAPIView.as_view(), name="site-publish"),
    path(
        "sites/<int:pk>/publish-versions",
        SitePublishVersionListAPIView.as_view(),
        name="site-publish-version-list",
    ),
    path(
        "sites/<int:pk>/publish-versions/<int:version_number>",
        SitePublishVersionDetailAPIView.as_view(),
        name="site-publish-version-detail",
    ),
    path(
        "sites/<int:pk>/rollback/<int:version_number>",
        SiteRollbackAPIView.as_view(),
        name="site-rollback",
    ),
]
