from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Page
from sites.models import Site
from .serializers import PageSerializer


class PageListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_site(self, site_pk, user):
        return get_object_or_404(Site, pk=site_pk, user=user)

    def get(self, request, site_pk):
        site = self.get_site(site_pk, request.user)
        pages = Page.objects.filter(site=site)
        serializer = PageSerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, site_pk):
        site = self.get_site(site_pk, request.user)
        serializer = PageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(site=site, created_by=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PageDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, site_pk, pk, user):
        site = get_object_or_404(Site, pk=site_pk, user=user)
        return get_object_or_404(Page, pk=pk, site=site)

    def get(self, request, site_pk, pk):
        page = self.get_object(site_pk, pk, request.user)
        serializer = PageSerializer(page)
        return Response(serializer.data)

    def put(self, request, site_pk, pk):
        page = self.get_object(site_pk, pk, request.user)
        serializer = PageSerializer(
            instance=page, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    def patch(self, request, site_pk, pk):
        page = self.get_object(site_pk, pk, request.user)
        serializer = PageSerializer(
            instance=page, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    def delete(self, request, site_pk, pk):
        page = self.get_object(site_pk, pk, request.user)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
