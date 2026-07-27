from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.pages.models import Page
from apps.pages.serializers import PageSerializer
from apps.sites.models import Site

User = get_user_model()


class PageSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="page_serializer_user", password="pass12345"
        )
        self.site = Site.objects.create(user=self.user, name="Serializer Test Site")
        self.factory = APIRequestFactory()

    def _context(self):
        request = self.factory.post("/fake-url/")
        request.user = self.user
        return {"site": self.site, "request": request}

    def test_valid_data_serializes_successfully(self):
        serializer = PageSerializer(
            data={"title": "My First Page"}, context=self._context()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_duplicate_slug_within_same_site_is_rejected(self):
        Page.objects.create(
            site=self.site,
            title="Existing Page",
            slug="existing-page",
            created_by=self.user,
        )
        serializer = PageSerializer(
            data={"title": "Existing Page"}, context=self._context()
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("title", serializer.errors)

    def test_same_title_allowed_on_different_site(self):
        other_site = Site.objects.create(user=self.user, name="Another Site")
        Page.objects.create(
            site=self.site,
            title="Shared Title",
            slug="shared-title",
            created_by=self.user,
        )
        context = {"site": other_site, "request": self.factory.post("/fake-url/")}
        context["request"].user = self.user
        serializer = PageSerializer(data={"title": "Shared Title"}, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_updating_same_instance_does_not_conflict_with_itself(self):
        page = Page.objects.create(
            site=self.site,
            title="Unchanged Title",
            slug="unchanged-title",
            created_by=self.user,
        )
        serializer = PageSerializer(
            page, data={"title": "Unchanged Title"}, context=self._context()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_site_slug_created_by_updated_by_are_read_only(self):
        other_site = Site.objects.create(user=self.user, name="Spoof Target Site")
        serializer = PageSerializer(
            data={
                "title": "Spoof Attempt",
                "site": other_site.id,
                "slug": "custom-slug",
                "created_by": self.user.id,
                "updated_by": self.user.id,
            },
            context=self._context(),
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        for field in ("site", "slug", "created_by", "updated_by"):
            self.assertNotIn(field, serializer.validated_data)
