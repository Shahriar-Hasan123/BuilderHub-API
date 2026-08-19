import io

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from apps.sites.models import ImageVariant, Site, SiteImage
from apps.sites.serializers import SiteImageSerializer, SiteSerializer

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


class SiteImageSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="image_serializer_user", password="pass12345"
        )
        self.site = Site.objects.create(user=self.user, name="Image Site")

    def _image(self, name="image.png", size=(200, 200), image_type="PNG"):
        output = io.BytesIO()
        Image.new("RGB", size, color="red").save(output, format=image_type)
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

    def test_create_optimizes_and_preserves_site_metadata(self):
        serializer = SiteImageSerializer(
            data={
                "image": self._image(),
                "image_type": SiteImage.ImageType.REGULAR,
                "alt_text": "A red image",
            },
            context={"site": self.site},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        image = serializer.save(site=self.site, created_by=self.user)

        self.assertEqual(image.site_id, self.site.id)
        self.assertEqual(image.file_name, "image.png")
        self.assertEqual(image.alt_text, "A red image")
        self.assertEqual(image.width, 200)
        self.assertEqual(image.height, 200)
        self.assertGreater(image.file_size, 0)
        self.assertTrue(image.image.name)

    def test_metadata_only_patch_does_not_require_image(self):
        image = SiteImage.objects.create(
            site=self.site,
            image=self._image(),
            image_type=SiteImage.ImageType.REGULAR,
        )
        serializer = SiteImageSerializer(
            image,
            data={"alt_text": "Updated text"},
            partial=True,
            context={"site": self.site},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()

        self.assertEqual(updated.alt_text, "Updated text")

    def test_create_generates_responsive_variants(self):
        serializer = SiteImageSerializer(
            data={
                "image": self._image(size=(2000, 1000)),
                "image_type": SiteImage.ImageType.REGULAR,
            },
            context={"site": self.site},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        image = serializer.save(site=self.site, created_by=self.user)

        variants = ImageVariant.objects.filter(image_upload=image)
        self.assertEqual(
            set(variants.values_list("variant_type", flat=True)),
            {"mobile", "laptop", "desktop"},
        )
        self.assertTrue(all(variant.image.name for variant in variants))
