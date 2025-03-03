#!/bin/sh



# Set default values if environment variables are not set
DB_HOST=${MYSQL_HOST:-db}
DB_PORT=${MYSQL_PORT:-3306}

# Wait for the database to be ready
/app/wait-for-it.sh "$DB_HOST" "$DB_PORT" -- echo "Database is ready!"

# If the first argument is "celery", run Celery directly.
if [ "$1" = "celery" ]; then
    shift
    exec celery "$@"
fi

python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=3

