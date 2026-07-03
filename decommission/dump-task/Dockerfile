# One-off image for logical DB export from inside the Copilot env VPC.
# postgres:16 provides pg_dump + psql (matches Aurora PG 16.11); add awscli + python3.
FROM postgres:16
RUN apt-get update \
    && apt-get install -y --no-install-recommends awscli ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*
COPY manifest.sql /manifest.sql
COPY dump.sh /usr/local/bin/dump.sh
RUN chmod +x /usr/local/bin/dump.sh
ENTRYPOINT ["/usr/local/bin/dump.sh"]
