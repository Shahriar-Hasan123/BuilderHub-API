from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.sites.models import Site


class HasUpdatePermission(BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        site = obj if isinstance(obj, Site) else obj.site
        return request.user == site.user or request.user.has_perm("sites.can_edit_site")