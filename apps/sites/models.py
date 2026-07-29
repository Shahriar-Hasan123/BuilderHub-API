from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.core.validators import (
    css_file_validator, html_file_validator,validate_file_size,
    validate_favicon_image, validate_logo_image, validate_thumbnail_image,
)


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

    url = models.URLField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    favicon = models.ImageField(
        upload_to="sites/favicons/",
        validators=[validate_favicon_image],
        blank=True,
        null=True,
    )
    logo = models.ImageField(
        upload_to="sites/logos/",
        validators=[validate_logo_image],
        blank=True,
        null=True,
    )
    thumbnail = models.ImageField(
        upload_to="sites/thumbnails/",
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
