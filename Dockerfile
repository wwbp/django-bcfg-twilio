FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    netcat-openbsd \
    curl \
    git \
    lsof \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --upgrade pip pipenv

COPY Pipfile Pipfile.lock ./

### PRODUCTION ###
FROM base AS production

RUN pipenv install --deploy --system

COPY . .

EXPOSE 8000

COPY ./entrypoint.prod.sh /entrypoint.prod.sh
RUN sed -i 's/\r$//g' /entrypoint.prod.sh
RUN chmod +x /entrypoint.prod.sh


### DEVELOPMENT ###
FROM base AS development

RUN pipenv install --dev --system

# Install pip requirements
WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser
