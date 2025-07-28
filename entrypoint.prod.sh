#!/bin/sh

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py migrate django_celery_results --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=5

