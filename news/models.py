from uuid import uuid4

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Ad')
    slug = models.SlugField(
        max_length=150, unique=True, allow_unicode=True, verbose_name='Slug',
    )
    description = models.TextField(blank=True, verbose_name='Təsvir')

    class Meta:
        ordering = ['name']
        verbose_name = 'Kateqoriya'
        verbose_name_plural = 'Kateqoriyalar'

    def __str__(self):
        return self.name


class News(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'

    title = models.CharField(max_length=255, verbose_name='Başlıq')
    slug = models.SlugField(
        max_length=300, unique=True, allow_unicode=True, blank=True,
        verbose_name='Slug',
    )
    summary = models.TextField(blank=True, verbose_name='Qısa məzmun')
    content = models.TextField(
        blank=True, verbose_name='Məzmun və ya mənbə haqqında məlumat',
    )
    image_url = models.URLField(
        max_length=2048, blank=True, verbose_name='Şəkil linki',
    )
    source = models.CharField(max_length=200, verbose_name='Mənbə')
    original_url = models.URLField(
        max_length=2048, unique=True, verbose_name='Orijinal xəbər linki',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='news',
        null=True,
        blank=True,
        verbose_name='Kateqoriya',
    )
    published_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Mənbədə dərc olunma vaxtı',
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Toplanma vaxtı',
    )
    views_count = models.PositiveIntegerField(default=0, verbose_name='Baxış sayı')
    priority = models.PositiveSmallIntegerField(default=0, verbose_name='Prioritet')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
        verbose_name='Status',
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Yaradılma vaxtı',
    )

    class Meta:
        ordering = ['-priority', '-published_at', '-created_at']
        verbose_name = 'Xəbər'
        verbose_name_plural = 'Xəbərlər'
        indexes = [models.Index(fields=['status', '-published_at'])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            title_slug = slugify(self.title, allow_unicode=True)[:250]
            self.slug = f'{title_slug or "xeber"}-{uuid4().hex}'
        super().save(*args, **kwargs)
