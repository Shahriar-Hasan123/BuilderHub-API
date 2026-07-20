from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

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
        self.enforce_site_lock(request, site)
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
        site.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
