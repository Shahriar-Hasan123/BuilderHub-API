from .models import Site
from .serializers import SiteSerializer
from rest_framework import viewsets, permissions


class SiteViewSet(viewsets.ModelViewSet):
    serializer_class = SiteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Site.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
