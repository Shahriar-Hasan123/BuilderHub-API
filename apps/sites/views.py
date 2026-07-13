from .models import Site
from .serializers import SiteSerializer
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404


class SiteListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sites = Site.objects.filter(user=request.user)
        serializer = SiteSerializer(sites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SiteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SiteDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(Site, pk=pk, user=user)

    def get(self, request, pk):
        site = self.get_object(pk, request.user)
        serializer = SiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        site = self.get_object(pk, request.user)
        serializer = SiteSerializer(instance=site, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        site = self.get_object(pk, request.user)
        serializer = SiteSerializer(instance=site, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        site = self.get_object(pk, request.user)
        site.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)