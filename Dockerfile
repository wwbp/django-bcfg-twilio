FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip pipenv

COPY Pipfile Pipfile.lock ./

RUN pipenv install --deploy --system

COPY . .

EXPOSE 8000

COPY ./entrypoint.prod.sh /entrypoint.prod.sh
RUN sed -i 's/\r$//g' /entrypoint.prod.sh
RUN chmod +x /entrypoint.prod.sh
