from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services.resource_lock import SiteLockService
from apps.core.exceptions import (
    ResourceLockedError,
    LockNotHeldError,
    SiteLockedAPIException,
    NoActiveLockAPIException,
)
from apps.core.mixins import SiteLockMixin

from .models import Site
from .serializers import SiteSerializer
from drf_spectacular.utils import extend_schema


class SiteListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Sites"],
        summary="List sites",
        description="Return all sites available to authenticated users.",
    )
    def get(self, request):
        sites = Site.objects.all()
        serializer = SiteSerializer(sites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Create site",
        description="Create a new site for the authenticated user.",
    )
    def post(self, request):
        serializer = SiteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SiteDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Site, pk=pk)

    @extend_schema(
        tags=["Sites"],
        summary="Get site",
        description="Retrieve a single site by its ID.",
    )
    def get(self, request, pk):
        site = self.get_object(pk)
        serializer = SiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Sites"],
        summary="Update site",
        description="Update an existing site completely.",
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
    )
    def delete(self, request, pk):
        site = self.get_object(pk)
        self.enforce_site_lock(request, site)
        site_id = site.id
        site.delete()
        SiteLockService().clear(site_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SiteLockAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_site(self, pk):
        return get_object_or_404(Site, pk=pk)

    def get(self, request, pk):
        site = self.get_site(pk)
        return Response(SiteLockService().status(site.id))

    def post(self, request, pk):
        site = self.get_site(pk)
        service = SiteLockService()
        try:
            service.acquire(site.id, request.user)
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(detail=f"This site is currently being edited by {exc.locked_by}.")
        return Response(service.status(site.id), status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        site = self.get_site(pk)
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
