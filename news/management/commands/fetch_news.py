from calendar import timegm
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import feedparser
import requests

from django.core.management.base import BaseCommand, CommandError
from django.utils.html import strip_tags

from news.models import Category, News
from news.utils import current_month_bounds


FEEDS = [
    {
        'url': 'https://oxu.az/feed',
        'source': 'Oxu.az',
        'host': 'oxu.az',
        'category': 'Yerli xəbərlər',
    },
    {
        'url': 'https://www.ayna.az/rss/category/iqtisadiyyat',
        'source': 'Ayna.az',
        'host': 'ayna.az',
        'category': 'İqtisadiyyat',
    },
]

CATEGORY_SLUGS = {
    'Siyasət': 'siyaset',
    'İqtisadiyyat': 'iqtisadiyyat',
    'İdman': 'idman',
    'Texnologiya': 'texnologiya',
    'Dünya': 'dunya',
    'Yerli xəbərlər': 'yerli-xeberler',
}

CATEGORY_NAMES = {
    'Siyasət': 'Siyasət',
    'İqtisadiyyat': 'İqtisadiyyat',
    'İdman': 'İdman',
    'İKT': 'Texnologiya',
    'Texnologiya': 'Texnologiya',
    'Dünya': 'Dünya',
    'Cəmiyyət': 'Yerli xəbərlər',
    'Hadisə': 'Yerli xəbərlər',
}


def is_web_url(value):
    try:
        parts = urlsplit(value)
        return parts.scheme in ('http', 'https') and bool(parts.netloc)
    except ValueError:
        return False


def is_source_url(value, host):
    if not is_web_url(value):
        return False
    return urlsplit(value).hostname in (host, f'www.{host}')


def clean_text(value):
    return ' '.join(unescape(strip_tags(value)).split())


def get_published_at(entry):
    parsed_date = entry.get('published_parsed')
    if not parsed_date:
        return None
    try:
        return datetime.fromtimestamp(timegm(parsed_date), tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


class ArticleMetadata(HTMLParser):
    """Read metadata and plain-text paragraphs inside the article only."""

    VOID_TAGS = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr',
    }
    BLOCK_TAGS = {'p', 'h2', 'h3', 'h4', 'li', 'blockquote'}
    IGNORED_TAGS = {'script', 'style', 'iframe', 'nav', 'aside', 'form', 'button'}
    ARTICLE_CLASSES = {'post-detail-content-inner', 'full-post-article'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metadata = {}
        self.stack = []
        self.root_index = None
        self.buffer = []
        self.paragraphs = []

    def flush_paragraph(self):
        text = ' '.join(''.join(self.buffer).split())
        self.buffer = []
        if text and (not self.paragraphs or text != self.paragraphs[-1]):
            self.paragraphs.append(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta':
            key = values.get('property') or values.get('name', '')
            if values.get('content'):
                self.metadata.setdefault(key, values['content'])

        if tag in self.VOID_TAGS:
            if tag == 'br' and self.root_index is not None:
                self.buffer.append(' ')
            return

        classes = set(values.get('class', '').split())
        blocked = tag in self.IGNORED_TAGS or bool(self.stack and self.stack[-1][1])
        self.stack.append((tag, blocked))

        if self.root_index is None and not blocked:
            if classes & self.ARTICLE_CLASSES or values.get('itemprop') == 'articleBody':
                self.root_index = len(self.stack) - 1

        if self.root_index is not None and tag in self.BLOCK_TAGS and not blocked:
            self.flush_paragraph()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.root_index is not None and self.stack and not self.stack[-1][1]:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        matching_index = next(
            (index for index in range(len(self.stack) - 1, -1, -1)
             if self.stack[index][0] == tag),
            None,
        )
        if matching_index is None:
            return

        if self.root_index is not None:
            if tag in self.BLOCK_TAGS and not self.stack[matching_index][1]:
                self.flush_paragraph()
            if matching_index <= self.root_index:
                self.flush_paragraph()
                self.root_index = None

        del self.stack[matching_index:]

    @property
    def excerpt(self):
        return next((text[:500] for text in self.paragraphs if len(text) >= 40), '')

    @property
    def article_text(self):
        return '\n\n'.join(self.paragraphs)


def get_feed_image(entry):
    # Prefer full media and image enclosures before small thumbnails.
    media = entry.get('media_content', [])
    enclosures = [
        {'url': item.get('href', '')}
        for item in entry.get('enclosures', [])
        if item.get('type', '').startswith('image/')
    ]
    for image in media + enclosures + entry.get('media_thumbnail', []):
        url = image.get('url', '')
        if is_web_url(url) and len(url) <= 2048:
            return url
    return ''


def get_article_metadata(session, url):
    parser = ArticleMetadata()
    response = session.get(url, timeout=(5, 15))
    response.raise_for_status()
    parser.feed(response.content.decode('utf-8', errors='replace'))

    image_url = ''
    for key in ('og:image:secure_url', 'og:image', 'twitter:image'):
        candidate = parser.metadata.get(key, '')
        if candidate:
            candidate = urljoin(response.url, candidate)
            if is_web_url(candidate) and len(candidate) <= 2048:
                image_url = candidate
                break

    description = (
        parser.metadata.get('og:description')
        or parser.metadata.get('description')
        or parser.excerpt
    )
    return image_url, clean_text(description)[:500], parser.article_text


def fetch_entry_details(entry):
    """Fetch article data; database writes stay in the main thread."""
    try:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'NewsPortalCourseProject/1.0'
            image, description, content = get_article_metadata(session, entry['link'])
        return image, description, content, ''
    except requests.RequestException as error:
        return '', '', '', str(error)


class Command(BaseCommand):
    help = 'Azərbaycan mənbələrindən yalnız cari ayın xəbərlərini toplayır.'

    def handle(self, *args, **options):
        month_start, now = current_month_bounds()
        added = 0
        refreshed = 0
        skipped = 0
        detail_failures = 0
        successful_sources = 0
        categories = {}

        with requests.Session() as session:
            session.headers['User-Agent'] = 'NewsPortalCourseProject/1.0'

            for config in FEEDS:
                try:
                    response = session.get(config['url'], timeout=(5, 20))
                    response.raise_for_status()
                except requests.RequestException as error:
                    self.stderr.write(f"{config['source']}: {error}")
                    continue

                feed = feedparser.parse(response.content)
                if not feed.entries:
                    self.stderr.write(f"{config['source']}: xəbər tapılmadı.")
                    continue

                successful_sources += 1
                self.stdout.write(
                    f"{config['source']}: RSS-də {len(feed.entries)} xəbər var."
                )

                existing = {
                    item.original_url: item
                    for item in News.objects.filter(source=config['source'])
                }
                pending = []
                seen_urls = set()
                for entry in feed.entries:
                    published_at = get_published_at(entry)
                    if published_at is None or not month_start <= published_at <= now:
                        continue

                    title = clean_text(entry.get('title', ''))[:255]
                    url = entry.get('link', '').strip()
                    if not title or len(url) > 2048:
                        continue
                    if not is_source_url(url, config['host']) or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    item = existing.get(url)
                    has_details = item and (
                        item.content
                        and not item.content.startswith('Mənbə:')
                        and item.content != item.summary
                        and item.image_url
                    )
                    if has_details:
                        skipped += 1
                        continue

                    entry['link'] = url
                    pending.append((entry, item))

                self.stdout.write(
                    f"{config['source']}: {len(pending)} xəbər işlənəcək."
                )

                # Four network requests at a time; no item count limit within this month.
                # Existing detailed records are reused on later manual runs.
                with ThreadPoolExecutor(max_workers=4) as executor:
                    results = executor.map(
                        fetch_entry_details,
                        (entry for entry, _ in pending),
                    )
                    for index, ((entry, old_item), result) in enumerate(
                        zip(pending, results), start=1,
                    ):
                        image_url, description, content, error = result
                        if error:
                            detail_failures += 1

                        summary = clean_text(entry.get('summary', ''))[:500]
                        summary = summary or description
                        image_url = image_url or get_feed_image(entry)

                        category_name = config['category']
                        for tag in entry.get('tags', []):
                            if tag.get('term') in CATEGORY_NAMES:
                                category_name = CATEGORY_NAMES[tag['term']]
                                break
                        if category_name not in categories:
                            categories[category_name], _ = Category.objects.get_or_create(
                                name=category_name,
                                defaults={'slug': CATEGORY_SLUGS[category_name]},
                            )

                        item, created = News.objects.get_or_create(
                            original_url=entry['link'],
                            defaults={
                                'title': clean_text(entry.get('title', ''))[:255],
                                'summary': summary,
                                'content': content or summary,
                                'image_url': image_url,
                                'source': config['source'],
                                'category': categories[category_name],
                                'published_at': get_published_at(entry),
                                'status': News.Status.PUBLISHED,
                            },
                        )
                        if created:
                            added += 1
                        else:
                            changes = {}
                            if image_url and image_url != item.image_url:
                                changes['image_url'] = image_url
                            if summary and not item.summary:
                                changes['summary'] = summary
                            if content and (
                                not item.content
                                or item.content.startswith('Mənbə:')
                                or item.content == item.summary
                            ):
                                changes['content'] = content
                            if changes:
                                News.objects.filter(pk=item.pk).update(**changes)
                                refreshed += 1

                        if index % 25 == 0 or index == len(pending):
                            self.stdout.write(
                                f"{config['source']}: {index}/{len(pending)} işlənib. "
                                f'Cəmi {added} yeni xəbər.'
                            )

        if successful_sources == 0:
            raise CommandError('Heç bir mənbədən xəbər alınmadı.')

        self.stdout.write(self.style.SUCCESS(
            f'Tamamlandı. {added} yeni, {refreshed} yenilənmiş, '
            f'{skipped} artıq mövcud xəbər.'
        ))
        if detail_failures:
            self.stdout.write(self.style.WARNING(
                f'{detail_failures} xəbərin səhifəsi alınmadı; RSS məlumatı saxlandı. '
                'Növbəti işə salmada yenidən yoxlanacaq.'
            ))
