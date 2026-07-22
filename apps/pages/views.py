from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SiteLockMixin
from apps.sites.models import Site

from .models import Page
from .serializers import PageSerializer
from apps.core.permissions import HasUpdatePermission


class PageListCreateAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, site_pk):
        site = get_object_or_404(Site, pk=site_pk)
        self.check_object_permissions(self.request, site)
        return site

    @extend_schema(
        tags=["Pages"],
        summary="List pages",
        description="Return all pages belonging to a specific site.",
    )
    def get(self, request, site_pk):
        site = self.get_site(site_pk)
        pages = Page.objects.filter(site=site)
        serializer = PageSerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Pages"],
        summary="Create page",
        description="Create a new page under a specific site.",
    )
    def post(self, request, site_pk):
        site = self.get_site(site_pk)
        self.enforce_site_lock(request, site)
        serializer = PageSerializer(
            data=request.data,
            context={
                "site": site,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(site=site, created_by=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PageDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, site_pk, pk):
        site = get_object_or_404(Site, pk=site_pk)
        page = get_object_or_404(Page, pk=pk, site=site)
        self.check_object_permissions(self.request, page)
        return site, page

    @extend_schema(
        tags=["Pages"],
        summary="Get page",
        description="Retrieve a single page by its ID.",
    )
    def get(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        serializer = PageSerializer(page)
        return Response(serializer.data)

    @extend_schema(
        tags=["Pages"],
        summary="Update page",
        description="Update an existing page completely.",
    )
    def put(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        serializer = PageSerializer(
            instance=page,
            data=request.data,
            context={
                "site": page.site,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=["Pages"],
        summary="Patch page",
        description="Partially update an existing page.",
    )
    def patch(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        serializer = PageSerializer(
            instance=page,
            data=request.data,
            partial=True,
            context={
                "site": page.site,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=["Pages"],
        summary="Delete page",
        description="Delete a page by its ID.",
    )
    def delete(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
