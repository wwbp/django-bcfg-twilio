#!/bin/sh

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py migrate django_celery_results --noinput
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers=5 \
  --worker-class=gthread \
  --threads=4 \
  --timeout=120 \
  --keep-alive=5 \
  --max-requests=1000 \
  --max-requests-jitter=100



