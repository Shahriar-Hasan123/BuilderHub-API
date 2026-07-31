from django.shortcuts import get_object_or_404
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
from apps.core.schema import object_response, site_schema, site_schema_view
from apps.core.services.resource_lock import SiteLockService
from apps.sites.services.publish_service import PublishService
from apps.sites.services.site_image_upload_service import SiteImageUploadService

from .models import Site, SiteImage
from .serializers import SiteImageSerializer, SiteSerializer


@site_schema_view(
    get=site_schema(
        "List sites",
        "Return all sites available to authenticated users.",
        responses=SiteSerializer(many=True),
    ),
    post=site_schema(
        "Create site",
        "Create a new site for the authenticated user.",
        request=SiteSerializer,
        responses=SiteSerializer,
    ),
)
class SiteListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sites = Site.objects.all()
        serializer = SiteSerializer(sites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SiteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(
            user=request.user, created_by=request.user, updated_by=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@site_schema_view(
    get=site_schema(
        "Get site",
        "Retrieve a single site by its ID.",
        responses=SiteSerializer,
    ),
    put=site_schema(
        "Update site",
        "Update an existing site completely.",
        request=SiteSerializer,
        responses=SiteSerializer,
    ),
    patch=site_schema(
        "Patch site",
        "Partially update an existing site.",
        request=SiteSerializer,
        responses=SiteSerializer,
    ),
    delete=site_schema(
        "Delete site",
        "Delete a site by its ID.",
        responses={204: None},
    ),
)
class SiteDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, pk):
        site = get_object_or_404(Site, pk=pk)
        self.check_object_permissions(self.request, site)
        return site

    def get(self, request, pk):
        site = self.get_object(pk)
        serializer = SiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        serializer = SiteSerializer(
            instance=site, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        serializer = SiteSerializer(
            instance=site, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        site_id = site.id
        site.delete()
        SiteLockService().clear(site_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@site_schema_view(
    get=site_schema(
        "Get lock status",
        "Return the current lock status for a site.",
        responses=object_response(),
    ),
    post=site_schema(
        "Acquire site lock",
        "Acquire or refresh a lock for editing a site.",
        responses=object_response(),
    ),
    patch=site_schema(
        "Refresh site lock",
        "Refresh the current lock holder's activity for a site.",
        responses=object_response(),
    ),
    delete=site_schema(
        "Release site lock",
        "Release a site lock that you currently hold.",
        responses={204: None},
    ),
)
class SiteLockAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, pk):
        site = get_object_or_404(Site, pk=pk)
        self.check_object_permissions(self.request, site)
        return site

    def get(self, request, pk):
        site = self.get_site(pk)
        return Response(SiteLockService().status(site.id))

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


@site_schema_view(
    get=site_schema(
        "List site images",
        "Return all images for a specific site.",
        responses=SiteImageSerializer(many=True),
    ),
    post=site_schema(
        "Create site image",
        "Upload a new image for a specific site.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    ),
)
class SiteImageListAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, site_pk):
        site = get_object_or_404(Site, pk=site_pk)
        self.check_object_permissions(self.request, site)
        return site

    def get(self, request, site_pk):
        site = self.get_site(site_pk)
        images = SiteImage.objects.filter(site=site)
        serializer = SiteImageSerializer(images, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, site_pk):
        site = self.get_site(site_pk)
        self.enforce_site_lock(request, site)

        service = SiteImageUploadService(
            site=site,
            user=request.user,
        )

        result = service.upload(request)
        return Response(
            {
                "uploaded": len(result["uploaded"]),
                "failed": len(result["failed"]),
                "success": result["uploaded"],
                "errors": result["failed"],
            },
            status=status.HTTP_201_CREATED,
        )


@site_schema_view(
    get=site_schema(
        "Get site image",
        "Retrieve a specific image belonging to a site.",
        responses=SiteImageSerializer,
    ),
    put=site_schema(
        "Update site image",
        "Update metadata or replace a site image.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    ),
    patch=site_schema(
        "Partially update site image",
        "Apply partial updates to a site image.",
        request=SiteImageSerializer,
        responses=SiteImageSerializer,
    ),
    delete=site_schema(
        "Delete site image",
        "Delete a site image by its ID.",
        responses={204: None},
    ),
)
class SiteImageDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, site_pk, pk):
        site = get_object_or_404(Site, pk=site_pk)
        image = get_object_or_404(SiteImage, pk=pk, site=site)
        self.check_object_permissions(self.request, image)
        return site, image

    def get(self, request, site_pk, pk):
        _, image = self.get_object(site_pk, pk)
        serializer = SiteImageSerializer(image)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, site_pk, pk):
        site, image = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        serializer = SiteImageSerializer(
            instance=image,
            data=request.data,
            context={"site": site},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, site_pk, pk):
        site, image = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        serializer = SiteImageSerializer(
            instance=image,
            data=request.data,
            partial=True,
            context={"site": site},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, site_pk, pk):
        site, image = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@site_schema_view(
    post=site_schema(
        "Publish site",
        (
            "Generate JSON asset files for the site header, footer, and enabled "
            "pages, then mark the site and pages as published."
        ),
        responses=object_response(),
    ),
)
class SitePublishAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, pk):
        return get_object_or_404(Site, pk=pk)

    def post(self, request, pk):
        site = self.get_site(pk)
        self.check_object_permissions(request, site)
        self.enforce_site_lock(request, site)
        try:
            result = PublishService().publish(site)
        except PublishValidationError as exc:
            raise DRFValidationError(str(exc))

        return Response(result, status=status.HTTP_200_OK)
