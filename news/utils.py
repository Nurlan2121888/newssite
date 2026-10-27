from zoneinfo import ZoneInfo

from django.utils import timezone


def current_month_bounds(now=None):
    """Return the current month's start and current time in Baku."""
    local_now = timezone.localtime(
        now or timezone.now(),
        ZoneInfo('Asia/Baku'),
    )
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start, local_now
