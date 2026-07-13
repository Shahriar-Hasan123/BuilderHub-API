from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Page
from .serializers import PageSerializer


class PageListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pages = Page.objects.filter(site__user=request.user)
        serializer = PageSerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = PageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PageDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(Page, pk=pk, site__user=user)

    def get(self, request, pk):
        page = self.get_object(pk, request.user)
        serializer = PageSerializer(page)
        return Response(serializer.data)

    def put(self, request, pk):
        page = self.get_object(pk, request.user)
        serializer = PageSerializer(instance=page, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    def patch(self, request, pk):
        page = self.get_object(pk, request.user)
        serializer = PageSerializer(instance=page, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    def delete(self, request, pk):
        page = self.get_object(pk, request.user)
        page.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)