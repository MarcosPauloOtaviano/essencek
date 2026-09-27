import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import RateLimitBucket

logger = logging.getLogger('django.security')


def _key(scope, identifier):
    source = f'{scope}:{identifier}'.encode('utf-8')
    return hashlib.sha256(source).hexdigest()


def _cache_key(scope, identifier):
    return f'rate_limit:{_key(scope, identifier)}'


def _database_hit(key, window_seconds):
    now = timezone.now()
    expires_at = now + timedelta(seconds=window_seconds)
    try:
        # Amortized cleanup keeps the shared table bounded without a cron job.
        if key.startswith('00'):
            RateLimitBucket.objects.filter(expires_at__lte=now).delete()
        with transaction.atomic():
            bucket, created = RateLimitBucket.objects.select_for_update().get_or_create(
                pk=key,
                defaults={'count': 1, 'expires_at': expires_at},
            )
            if created:
                return 1, expires_at
            if bucket.expires_at <= now:
                bucket.count = 1
                bucket.expires_at = expires_at
            else:
                bucket.count += 1
            bucket.save(update_fields=['count', 'expires_at', 'updated_at'])
            return bucket.count, bucket.expires_at
    except DatabaseError:
        logger.exception('Shared rate limit unavailable; request allowed')
        return 0, expires_at


def _database_reset(key):
    try:
        RateLimitBucket.objects.filter(pk=key).delete()
    except DatabaseError:
        logger.exception('Unable to reset shared rate limit counter')


def hit(scope, identifier, limit, window_seconds):
    """Increment a counter and return (blocked, count, retry_after_seconds)."""
    key = _key(scope, identifier)
    if getattr(settings, 'SHARED_RATE_LIMIT_ENABLED', False):
        count, expires_at = _database_hit(key, window_seconds)
        retry_after = max(1, int((expires_at - timezone.now()).total_seconds()))
    else:
        cache_key = _cache_key(scope, identifier)
        count = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, window_seconds)
        retry_after = window_seconds
    return count > limit, count, retry_after


def reset(scope, identifier):
    key = _key(scope, identifier)
    if getattr(settings, 'SHARED_RATE_LIMIT_ENABLED', False):
        _database_reset(key)
    else:
        cache.delete(_cache_key(scope, identifier))
