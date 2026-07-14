from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel
from apps.core.validators import (
    css_file_validator,
    html_file_validator,
    validate_file_size,
)
from apps.sites.models import Site


class Page(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class PageType(models.TextChoices):
        STANDARD = "standard", "Standard"
        LANDING = "landing", "Landing Page"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pages")
    title = models.CharField(max_length=255)
    slug = models.SlugField(blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    page_type = models.CharField(
        max_length=20, choices=PageType.choices, default=PageType.STANDARD
    )
    enable = models.BooleanField(default=True)
    canonical_url = models.URLField(blank=True)
    html = models.FileField(
        upload_to="pages/html/",
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    css = models.FileField(
        upload_to="pages/css/",
        validators=[css_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pages_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pages_updated",
    )

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_slug_per_site"
            ),
        ]

    def save(self, user=None, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.site.name})"
