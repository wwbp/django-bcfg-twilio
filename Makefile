migrations:
	python manage.py makemigrations

empty-migration:
	python manage.py makemigrations --empty chat

migrate:
	python manage.py migrate

lint:
	ruff check . --fix

requirements:
	pipenv lock
	echo "Pipfile.lock updated, rebuild container to install new dependencies"

test:
	pytest -n 2 --cov=chat --cov-report=html:coverage/coverage.html --cov-context=test --cov-report term

clear-all-prompts:
	python manage.py clear_all_prompts

dump-all-prompts:
	mkdir -p chat/fixtures
	python manage.py dumpdata --format yaml chat.control chat.prompt -o chat/fixtures/all-prompts.yaml

load-all-prompts:
	mkdir -p chat/fixtures
	python manage.py loaddata chat/fixtures/all-prompts.yaml
