from django.contrib import admin

from .models import Category, News


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {
        'slug': ('name',),
    }


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'source',
        'category',
        'status',
        'priority',
        'views_count',
        'published_at',
    )
    list_filter = ('status', 'category', 'source')
    search_fields = ('title', 'summary', 'source')
    list_editable = ('status', 'priority')
    list_select_related = ('category',)
    readonly_fields = (
        'slug',
        'views_count',
        'fetched_at',
        'created_at',
    )
    date_hierarchy = 'published_at'
    actions = ['publish_news', 'reject_news']

    @admin.action(description='Seçilmiş xəbərləri dərc et')
    def publish_news(self, request, queryset):
        count = queryset.update(status=News.Status.PUBLISHED)

        self.message_user(
            request,
            f'{count} xəbər dərc edildi.',
        )

    @admin.action(description='Seçilmiş xəbərləri rədd et')
    def reject_news(self, request, queryset):
        count = queryset.update(status=News.Status.REJECTED)

        self.message_user(
            request,
            f'{count} xəbər rədd edildi.',
        )