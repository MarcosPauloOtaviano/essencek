import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from .models import RateLimitBucket

logger = logging.getLogger('django.security')


def _key(scope, identifier):
    source = f'{scope}:{identifier}'.encode('utf-8')
    return hmac.new(settings.PII_HASH_KEY.encode(), source, hashlib.sha256).hexdigest()


def _cache_key(scope, identifier):
    return f'rate_limit:{_key(scope, identifier)}'


def _database_hit(key, window_seconds):
    now = timezone.now()
    expires_at = now + timedelta(seconds=window_seconds)
    try:
        if connection.vendor == 'postgresql':
            # One atomic statement avoids lost updates and extra network trips
            # on the serverless hot path. No raw IP is persisted.
            with connection.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO core_ratelimitbucket (key, count, expires_at, updated_at)
                    VALUES (%s, 1, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET
                      count = CASE WHEN core_ratelimitbucket.expires_at <= EXCLUDED.updated_at
                              THEN 1 ELSE LEAST(core_ratelimitbucket.count + 1, 1000000000) END,
                      expires_at = CASE WHEN core_ratelimitbucket.expires_at <= EXCLUDED.updated_at
                                   THEN EXCLUDED.expires_at ELSE core_ratelimitbucket.expires_at END,
                      updated_at = EXCLUDED.updated_at
                    RETURNING count, expires_at
                ''', [key, expires_at, now])
                return cursor.fetchone()
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
        now = timezone.now()
        counter = cache.get(cache_key)
        if not counter or counter[1] <= now:
            counter = (0, now + timedelta(seconds=window_seconds))
        count, expires_at = counter[0] + 1, counter[1]
        retry_after = max(1, int((expires_at - now).total_seconds()))
        cache.set(cache_key, (count, expires_at), retry_after + 1)
    return count > limit, count, retry_after


def reset(scope, identifier):
    key = _key(scope, identifier)
    if getattr(settings, 'SHARED_RATE_LIMIT_ENABLED', False):
        _database_reset(key)
    else:
        cache.delete(_cache_key(scope, identifier))
