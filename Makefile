migrations:
	python manage.py makemigrations

empty-migration:
	python manage.py makemigrations --empty chat

migrate:
	python manage.py migrate
