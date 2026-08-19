from django.conf import settings
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify

from apps.core.models import BaseModel
from apps.core.validators import (
    css_file_validator,
    html_file_validator,
    validate_regular_image,
    validate_favicon_image,
    validate_file_size,
    validate_logo_image,
    validate_thumbnail_image,
)


@deconstructible
class SiteImageUploadTo:
    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        related_site = getattr(instance, "site", None)
        site_name = getattr(related_site, "name", None) or getattr(
            instance, "name", "site"
        )
        site_slug = slugify(site_name) or "site"

        related_page = getattr(instance, "page", None)
        if getattr(instance, "page_id", None) and related_page is not None:
            page_slug = slugify(getattr(related_page, "slug", "")) or slugify(
                getattr(related_page, "title", "page")
            )
            return f"sites/{site_slug}/pages/{page_slug}/{self.folder}/{filename}"
        return f"sites/{site_slug}/{self.folder}/{filename}"


@deconstructible
class SiteFileUploadTo:
    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        related_site = getattr(instance, "site", None)
        site_name = getattr(related_site, "name", None) or getattr(
            instance, "name", "site"
        )
        site_slug = slugify(site_name) or "site"
        return f"sites/{site_slug}/{self.folder}/{filename}"


class Site(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        SUSPENDED = "suspended", "Suspended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sites",
    )
    name = models.CharField(max_length=255, blank=False)

    url = models.URLField(blank=True, null=True, unique=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    favicon = models.ImageField(
        upload_to=SiteImageUploadTo("favicons"),
        validators=[validate_favicon_image],
        blank=True,
        null=True,
    )
    logo = models.ImageField(
        upload_to=SiteImageUploadTo("logos"),
        validators=[validate_logo_image],
        blank=True,
        null=True,
    )
    thumbnail = models.ImageField(
        upload_to=SiteImageUploadTo("thumbnails"),
        validators=[validate_thumbnail_image],
        blank=True,
        null=True,
    )
    global_css = models.FileField(
        upload_to=SiteFileUploadTo("css"),
        validators=[css_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sites_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sites_updated",
    )
    header = models.FileField(
        upload_to=SiteFileUploadTo("header"),
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    footer = models.FileField(
        upload_to=SiteFileUploadTo("footer"),
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
    )

    current_published_version = models.ForeignKey(
        "sites.SitePublishVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_site_name_global"),
        ]
        permissions = [("can_edit_site", "Can edit any site")]

    def __str__(self):
        return self.name


class SiteImage(BaseModel):

    class ImageType(models.TextChoices):
        REGULAR = "regular", "Regular"
        HERO = "hero", "Hero"
        THUMBNAIL = "thumbnail", "Thumbnail"
        FAVICON = "favicon", "Favicon"
        LOGO = "logo", "Logo"
    
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="images",
    )
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.SET_NULL,
        related_name="images",
        blank=True,
        null=True,
        help_text="Optional. Leave empty for site-wide reusable images.",
    )
    file_name = models.CharField(max_length=500, blank=True)

    image = models.ImageField(
        upload_to=SiteImageUploadTo("images"),
        validators=[validate_regular_image],
    )

    image_type = models.CharField(max_length=20, choices=ImageType.choices, default=ImageType.REGULAR)
    alt_text = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(
        blank=True, null=True, help_text="Size in bytes, cached at save time."
    )
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_images_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_images_updated",
    )

    class Meta:
        verbose_name = "Site Image"
        verbose_name_plural = "Site Images"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Image ({self.site.name})" + (
            f" - {self.page.title}" if self.page_id else ""
        )


def upload_to_variant(instance, filename):
    return SiteImageUploadTo("variants")(instance.image_upload, filename)


class ImageVariant(models.Model):
    class VariantType(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        LAPTOP = "laptop", "Laptop"
        DESKTOP = "desktop", "Desktop"

    image_upload = models.ForeignKey(
        SiteImage,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    variant_type = models.CharField(
        max_length=10,
        choices=VariantType.choices,
    )
    image = models.FileField(upload_to=upload_to_variant)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    format = models.CharField(max_length=10)
    file_size = models.PositiveIntegerField(help_text="Size in bytes.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["image_upload", "variant_type"],
                name="unique_site_image_variant_type",
            ),
        ]
        ordering = ["width"]

    def __str__(self):
        return f"{self.image_upload.file_name} ({self.variant_type}, {self.width}x{self.height})"


class SitePublishVersion(BaseModel):
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name="publish_versions"
    )
    version_number = models.PositiveIntegerField()
    header_hash = models.CharField(max_length=256)
    footer_hash = models.CharField(max_length=256)
    page_hashes = models.JSONField(
        default=dict, help_text="Mapping of page slug to its content hash."
    )
    asset_hashes = models.JSONField(
        default=dict,
        help_text="Mapping of editable asset paths to their content hashes.",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_publish_versions",
    )

    class Meta:
        verbose_name = "Site Publish Version"
        verbose_name_plural = "Site Publish Versions"
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "version_number"], name="unique_site_version_number"
            ),
        ]

    def __str__(self):
        return f"{self.site.name} v{self.version_number}"
