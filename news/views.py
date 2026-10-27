from math import ceil

from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .models import Category, News
from .utils import current_month_bounds


def published_news():
    month_start, now = current_month_bounds()
    return News.objects.filter(
        status=News.Status.PUBLISHED,
        published_at__gte=month_start,
        published_at__lte=now,
    ).select_related('category')


def navigation_context():
    articles = published_news()
    _, now = current_month_bounds()
    return {
        'navigation_categories': Category.objects.filter(
            news__in=articles,
        ).distinct().order_by('name'),
        'total_news': articles.count(),
        'edition_date': now,
    }


def news_list(request):
    articles = published_news()
    selected_category = None
    category_slug = request.GET.get('category', '').strip()
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        articles = articles.filter(category=selected_category)

    news_items = list(articles)
    context = navigation_context()
    context.update({
        'news_items': news_items,
        'selected_category': selected_category,
        'lead_story': news_items[0] if news_items else None,
        'secondary_stories': news_items[1:3],
        'feed_stories': news_items[3:7],
        'grid_stories': news_items[3:],
    })
    return render(request, 'news/news_list.html', context)


def news_detail(request, slug):
    item = get_object_or_404(published_news(), slug=slug)
    if request.method == 'GET':
        News.objects.filter(pk=item.pk).update(views_count=F('views_count') + 1)
        item.refresh_from_db(fields=['views_count'])

    other_news = published_news().exclude(pk=item.pk)
    related_news = []
    if item.category_id:
        related_news = list(other_news.filter(category_id=item.category_id)[:4])

    related_heading = 'Eyni gündəmdə'
    related_description = 'Bu kateqoriyadan oxumağa davam et'
    if not related_news:
        related_news = list(other_news[:4])
        related_heading = 'Gündəm davam edir'
        related_description = 'Digər aktual xəbərlər'

    article_content = item.content
    if not article_content or article_content.startswith('Mənbə:'):
        article_content = item.summary

    context = navigation_context()
    context.update({
        'item': item,
        'selected_category': item.category,
        'article_content': article_content,
        'reading_minutes': max(1, ceil(len(article_content.split()) / 200)),
        'related_news': related_news,
        'related_heading': related_heading,
        'related_description': related_description,
    })
    return render(request, 'news/news_detail.html', context)
