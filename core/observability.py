"""Operational telemetry with no bodies, query strings, identities or secrets."""
import json
import logging
import time
import uuid
from datetime import datetime, timezone


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        data = {
            'time': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'event': 'request_failure' if record.levelno >= logging.ERROR else 'slow_request',
        }
        for key in ('request_id', 'route', 'status_code', 'duration_ms'):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


class RequestMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        elapsed = round((time.monotonic() - started) * 1000)
        if response.status_code >= 500 or elapsed >= 3000:
            match = getattr(request, 'resolver_match', None)
            logging.getLogger('store.operations').log(
                logging.ERROR if response.status_code >= 500 else logging.WARNING,
                'Request health event',
                extra={
                    'request_id': request_id,
                    'route': getattr(match, 'view_name', 'unresolved'),
                    'status_code': response.status_code,
                    'duration_ms': elapsed,
                },
            )
        return response


def sanitize_sentry_event(event, hint):
    """Keep useful error locations while dropping customer and request data."""
    for key in ('request', 'user', 'extra', 'breadcrumbs', 'contexts', 'logentry'):
        event.pop(key, None)
    event.pop('message', None)
    for exception in event.get('exception', {}).get('values', []):
        exception['value'] = '[details redacted]'
        for frame in exception.get('stacktrace', {}).get('frames', []):
            for key in ('vars', 'pre_context', 'post_context', 'context_line'):
                frame.pop(key, None)
    return event
