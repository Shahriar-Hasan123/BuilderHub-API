from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.sites.models import Site
from apps.sites.serializers import SiteSerializer

User = get_user_model()


class SiteSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="serializer_user", password="pass12345"
        )
        self.factory = APIRequestFactory()

    def _context(self):
        request = self.factory.post("/fake-url/")
        request.user = self.user
        return {"request": request}

    def test_valid_data_serializes_successfully(self):
        serializer = SiteSerializer(
            data={"name": "My Portfolio Site"}, context=self._context()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_duplicate_name_is_rejected(self):
        Site.objects.create(user=self.user, name="Existing Site")
        serializer = SiteSerializer(
            data={"name": "Existing Site"}, context=self._context()
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_updating_same_instance_does_not_conflict_with_itself(self):
        site = Site.objects.create(user=self.user, name="Unchanged Name")
        serializer = SiteSerializer(
            site, data={"name": "Unchanged Name"}, context=self._context()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_user_and_updated_by_are_read_only(self):
        other_user = User.objects.create_user(username="attacker", password="pass12345")
        serializer = SiteSerializer(
            data={
                "name": "Spoof Attempt",
                "user": other_user.id,
                "updated_by": other_user.id,
            },
            context=self._context(),
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("user", serializer.validated_data)
        self.assertNotIn("updated_by", serializer.validated_data)
