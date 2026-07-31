from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SiteLockMixin
from apps.core.permissions import HasUpdatePermission
from apps.core.schema import page_schema, page_schema_view
from apps.sites.models import Site

from .models import Page
from .serializers import PageSerializer


@page_schema_view(
    get=page_schema(
        "List pages",
        "Return all pages belonging to a specific site.",
        responses=PageSerializer(many=True),
    ),
    post=page_schema(
        "Create page",
        "Create a new page under a specific site.",
        request=PageSerializer,
        responses=PageSerializer,
    ),
)
class PageListCreateAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_site(self, site_pk):
        site = get_object_or_404(Site, pk=site_pk)
        self.check_object_permissions(self.request, site)
        return site

    def get(self, request, site_pk):
        site = self.get_site(site_pk)
        pages = Page.objects.filter(site=site)
        serializer = PageSerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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


@page_schema_view(
    get=page_schema(
        "Get page",
        "Retrieve a single page by its ID.",
        responses=PageSerializer,
    ),
    put=page_schema(
        "Update page",
        "Update an existing page completely.",
        request=PageSerializer,
        responses=PageSerializer,
    ),
    patch=page_schema(
        "Patch page",
        "Partially update an existing page.",
        request=PageSerializer,
        responses=PageSerializer,
    ),
    delete=page_schema(
        "Delete page",
        "Delete a page by its ID.",
        responses={204: None},
    ),
)
class PageDetailAPIView(APIView, SiteLockMixin):
    permission_classes = [permissions.IsAuthenticated, HasUpdatePermission]

    def get_object(self, site_pk, pk):
        site = get_object_or_404(Site, pk=site_pk)
        page = get_object_or_404(Page, pk=pk, site=site)
        self.check_object_permissions(self.request, page)
        return site, page

    def get(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        serializer = PageSerializer(page)
        return Response(serializer.data)

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

    def delete(self, request, site_pk, pk):
        site, page = self.get_object(site_pk, pk)
        self.enforce_site_lock(request, site)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
