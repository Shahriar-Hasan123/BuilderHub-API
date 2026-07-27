from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.core.permissions import HasUpdatePermission
from apps.pages.models import Page
from apps.sites.models import Site

User = get_user_model()


class HasUpdatePermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        self.editor = User.objects.create_user(username="editor", password="pass12345")
        self.stranger = User.objects.create_user(
            username="stranger", password="pass12345"
        )

        can_edit_perm = Permission.objects.get(codename="can_edit_site")
        self.editor.user_permissions.add(can_edit_perm)

        self.site = Site.objects.create(user=self.owner, name="Permission Test Site")
        self.page = Page.objects.create(
            site=self.site,
            title="Test Page",
            created_by=self.owner,
        )

        self.permission = HasUpdatePermission()
        self.factory = APIRequestFactory()

    def _request(self, method, user):
        request = getattr(self.factory, method.lower())("/fake-url/")
        request.user = user
        return request

    def test_safe_method_allowed_for_anyone(self):
        request = self._request("GET", self.stranger)
        self.assertTrue(self.permission.has_object_permission(request, None, self.site))

    def test_write_allowed_for_owner(self):
        request = self._request("PATCH", self.owner)
        self.assertTrue(self.permission.has_object_permission(request, None, self.site))

    def test_write_allowed_for_user_with_global_permission(self):
        request = self._request("PATCH", self.editor)
        self.assertTrue(self.permission.has_object_permission(request, None, self.site))

    def test_write_denied_for_user_without_permission(self):
        request = self._request("PATCH", self.stranger)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.site)
        )

    def test_write_on_page_resolves_permission_via_parent_site(self):
        request = self._request("PATCH", self.owner)
        self.assertTrue(self.permission.has_object_permission(request, None, self.page))

        request = self._request("PATCH", self.stranger)
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.page)
        )
