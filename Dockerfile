FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    pkg-config \
    netcat-openbsd \
    curl \
    git \
    lsof \
    xmlsec1 \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --upgrade pip pipenv

COPY Pipfile Pipfile.lock ./


### DEVELOPMENT ###
FROM base AS development

RUN pipenv install --dev --system

# install various tools
RUN curl -Lo copilot https://github.com/aws/copilot-cli/releases/latest/download/copilot-linux \
    && chmod +x copilot \
    && mv copilot /usr/local/bin/copilot \
    && copilot --help

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# setup AWS auth - using branch to get PR https://github.com/upenn/aws-federated-auth/pull/3
RUN pip install git+https://github.com/upenn/aws-federated-auth.git@feature/linux_keyring
ENV PATH="~/.local/bin:${PATH}"

# Install pip requirements
WORKDIR /app
COPY . /app


### PRODUCTION ###
# This must be last stage in the file due to a copilot bug not sending the correct target/build
# stage to the docker build command.
# This might be related to https://github.com/aws/copilot-cli/issues/5921
FROM base AS production

RUN pipenv install --deploy --system

COPY . .

EXPOSE 8000

COPY ./entrypoint.prod.sh /entrypoint.prod.sh
RUN sed -i 's/\r$//g' /entrypoint.prod.sh
RUN chmod +x /entrypoint.prod.sh
