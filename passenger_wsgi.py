import os
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Ensure the app directory is in sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Change to app directory so python-decouple finds .env
os.chdir(str(BASE_DIR))

os.environ['DJANGO_SETTINGS_MODULE'] = 'paraguashopping.settings.production'

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as exc:
    # Log startup errors to a file so we can debug
    log_path = BASE_DIR / 'logs' / 'passenger_startup.log'
    log_path.parent.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(log_path), level=logging.ERROR)
    logging.exception('Passenger startup failed')

    # Return a simple error response so we get 500 instead of silent 403
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [f'Application startup error: {exc}\nCheck ~/essencek_app/logs/passenger_startup.log'.encode()]
