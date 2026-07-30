from django.conf import settings
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify

from apps.core.models import BaseModel
from apps.core.validators import (
    css_file_validator,
    html_file_validator,
    validate_content_image,
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
        site_slug = (
            slugify(getattr(instance.site, "name", getattr(instance, "name", "site")))
            or "site"
        )
        if getattr(instance, "page_id", None):
            page_slug = slugify(getattr(instance.page, "slug", "")) or slugify(
                getattr(instance.page, "title", "page")
            )
            return f"sites/{site_slug}/pages/{page_slug}/{self.folder}/{filename}"
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
    name = models.CharField(max_length=255)

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
        upload_to="sites/css/",
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
        upload_to="sites/header/",
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    footer = models.FileField(
        upload_to="sites/footer/",
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
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
        validators=[validate_content_image],
    )
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
