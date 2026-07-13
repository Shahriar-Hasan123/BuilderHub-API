from django.conf import settings
from django.db import models
from apps.core.models import BaseModel
from apps.core.validators import validate_file_size, css_file_validator


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

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    favicon = models.ImageField(
        upload_to="sites/favicons/",
        validators=[validate_file_size],
        blank=True,
        null=True,
    )
    logo = models.ImageField(
        upload_to="sites/logos/",
        validators=[validate_file_size],
        blank=True,
        null=True,
    )
    global_css = models.FileField(
        upload_to="sites/css/",
        validators=[css_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sites_updated",
    )

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
