from django.conf import settings
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify

from apps.core.models import BaseModel
from apps.core.validators import (
    css_file_validator,
    html_file_validator,
    validate_file_size,
    validate_hero_image,
)
from apps.sites.models import Site


@deconstructible
class PageImageUploadTo:
    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        related_site = getattr(instance, "site", None)
        site_name = getattr(related_site, "name", None) or getattr(instance, "name", "site")
        site_slug = slugify(site_name) or "site"

        page_slug = slugify(getattr(instance, "slug", "")) or slugify(
            getattr(instance, "title", "page")
        )
        return f"sites/{site_slug}/pages/{page_slug}/{self.folder}/{filename}"


@deconstructible
class PageFileUploadTo:
    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        related_site = getattr(instance, "site", None)
        site_name = getattr(related_site, "name", None) or getattr(instance, "name", "site")
        site_slug = slugify(site_name) or "site"

        page_slug = slugify(getattr(instance, "slug", "")) or slugify(
            getattr(instance, "title", "page")
        )
        return f"sites/{site_slug}/pages/{page_slug}/{self.folder}/{filename}"


class Page(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class PageType(models.TextChoices):
        STANDARD = "standard", "Standard"
        LANDING = "landing", "Landing Page"
        BLOG = "blog", "Blog Page"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pages")
    title = models.CharField(max_length=255, blank=False)
    slug = models.SlugField(max_length=100, blank=True)
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
        upload_to=PageFileUploadTo("html"),
        validators=[html_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    css = models.FileField(
        upload_to=PageFileUploadTo("css"),
        validators=[css_file_validator, validate_file_size],
        blank=True,
        null=True,
    )
    hero_image = models.ImageField(
        upload_to=PageImageUploadTo("hero"),
        validators=[validate_hero_image],
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
