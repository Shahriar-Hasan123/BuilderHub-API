from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import (
    LockNotHeldError,
    NoActiveLockAPIException,
    PublishValidationError,
    ResourceLockedError,
    SiteLockedAPIException,
)
from apps.core.mixins import SiteLockMixin
from apps.core.permissions import HasUpdatePermission
from apps.core.services.resource_lock import SiteLockService
from apps.sites.services.publish_service import PublishService

from .models import Site, SiteImage
from .serializers import SiteImageSerializer, SiteSerializer


class SiteListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Sites"],
        summary="List sites",
        description="Return all sites available to authenticated users.",
        responses=SiteSerializer(many=True),
    )
    def get(self, request):
        sites = Site.objects.all()
        serializer = SiteSerializer(sites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Create site",
        description="Create a new site for the authenticated user.",
        request=SiteSerializer,
        responses=SiteSerializer,
    )
    def post(self, request):
        serializer = SiteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(
            user=request.user, created_by=request.user, updated_by=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SiteDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, pk):
        site = get_object_or_404(Site, pk=pk)
        self.check_object_permissions(self.request, site)
        return site

    @extend_schema(
        tags=["Sites"],
        summary="Get site",
        description="Retrieve a single site by its ID.",
        responses=SiteSerializer,
    )
    def get(self, request, pk):
        site = self.get_object(pk)
        serializer = SiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Update site",
        description="Update an existing site completely.",
        request=SiteSerializer,
        responses=SiteSerializer,
    )
    def put(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        serializer = SiteSerializer(
            instance=site, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Patch site",
        description="Partially update an existing site.",
        request=SiteSerializer,
        responses=SiteSerializer,
    )
    def patch(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        serializer = SiteSerializer(
            instance=site, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Delete site",
        description="Delete a site by its ID.",
        responses={204: None},
    )
    def delete(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        site_id = site.id
        site.delete()
        SiteLockService().clear(site_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SiteLockAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, pk):
        site = get_object_or_404(Site, pk=pk)
        self.check_object_permissions(self.request, site)
        return site

    @extend_schema(
        tags=["Sites"],
        summary="Get lock status",
        description="Return the current lock status for a site.",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request, pk):
        site = self.get_site(pk)
        return Response(SiteLockService().status(site.id))

    @extend_schema(
        tags=["Sites"],
        summary="Acquire site lock",
        description="Acquire or refresh a lock for editing a site.",
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request, pk):
        site = self.get_site(pk)
        try:
            result = SiteLockService().acquire(site.id, request.user)
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(
                detail=f"This site is currently being edited by {exc.locked_by}."
            )
        message = (
            "Lock acquired successfully."
            if result.created
            else "You already hold this lock - activity refreshed."
        )
        return Response(
            {
                "message": message,
                "locked": True,
                "created": result.created,
                "user_id": result.user_id,
                "locked_by": result.username,
                "locked_at": result.locked_at,
                "last_activity_at": result.last_activity_at,
                "ttl_remaining_seconds": result.ttl_remaining_seconds,
            },
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Sites"],
        summary="Refresh site lock",
        description="Refresh the current lock holder's activity for a site.",
        responses=OpenApiTypes.OBJECT,
    )
    def patch(self, request, pk):
        site = self.get_site(pk)
        self.check_object_permissions(request, site)
        service = SiteLockService()
        try:
            service.refresh(site.id, request.user)
        except LockNotHeldError:
            raise NoActiveLockAPIException()
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(
                detail=f"This site is locked by {exc.locked_by}, not you."
            )

        return Response(service.status(site.id), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Release site lock",
        description="Release a site lock that you currently hold.",
        responses={204: None},
    )
    def delete(self, request, pk):
        site = get_object_or_404(Site, pk=pk)
        self.check_object_permissions(request, site)
        service = SiteLockService()
        try:
            service.release(site.id, request.user)
        except LockNotHeldError:
            raise NoActiveLockAPIException()
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(
                detail=f"This site is locked by {exc.locked_by}, not you."
            )
        return Response({"detail": "Lock released."}, status=status.HTTP_204_NO_CONTENT)


class SiteImageListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, site_pk):
        site = get_object_or_404(Site, pk=site_pk)
        self.check_object_permissions(self.request, site)
        return site

    @extend_schema(
        tags=["Sites"],
        summary="List site images",
        description="Return all images for a specific site.",
        responses=SiteImageSerializer(many=True),
    )
    def get(self, request, site_pk):
        site = self.get_site(site_pk)
        images = SiteImage.objects.filter(site=site)
        serializer = SiteImageSerializer(images, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Create site image",
        description="Upload a new image for a specific site.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    )
    def post(self, request, site_pk):
        site = self.get_site(site_pk)
        serializer = SiteImageSerializer(
            data=request.data,
            context={"site": site},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            site=site,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SiteImageDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, site_pk, pk):
        site = get_object_or_404(Site, pk=site_pk)
        image = get_object_or_404(SiteImage, pk=pk, site=site)
        self.check_object_permissions(self.request, image)
        return site, image

    @extend_schema(
        tags=["Sites"],
        summary="Get site image",
        description="Retrieve a specific image belonging to a site.",
        responses=SiteImageSerializer,
    )
    def get(self, request, site_pk, pk):
        _, image = self.get_object(site_pk, pk)
        serializer = SiteImageSerializer(image)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Update site image",
        description="Update metadata or replace a site image.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    )
    def put(self, request, site_pk, pk):
        site, image = self.get_object(site_pk, pk)
        serializer = SiteImageSerializer(
            instance=image,
            data=request.data,
            context={"site": site},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Partially update site image",
        description="Apply partial updates to a site image.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    )
    def patch(self, request, site_pk, pk):
        site, image = self.get_object(site_pk, pk)
        serializer = SiteImageSerializer(
            instance=image,
            data=request.data,
            partial=True,
            context={"site": site},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Delete site image",
        description="Delete a site image by its ID.",
        responses={204: None},
    )
    def delete(self, request, site_pk, pk):
        _, image = self.get_object(site_pk, pk)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SitePublishAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, pk):
        return get_object_or_404(Site, pk=pk)

    @extend_schema(
        tags=["Sites"],
        summary="Publish site",
        description=(
            "Generate JSON asset files for the site header, footer, and enabled "
            "pages, then mark the site and pages as published."
        ),
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request, pk):
        site = self.get_site(pk)
        self.check_object_permissions(request, site)
        self.enforce_site_lock(request, site)
        try:
            result = PublishService().publish(site)
        except PublishValidationError as exc:
            raise DRFValidationError(str(exc))

        return Response(result, status=status.HTTP_200_OK)
