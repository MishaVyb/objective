FROM python:3.11.4-slim-bullseye as prod

RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*


RUN pip install poetry==2.1.3

# Configuring poetry
RUN poetry config virtualenvs.create false

# Copying requirements of a project to /app/src
COPY pyproject.toml poetry.lock /app/src/

# Set workdir
WORKDIR /app/src

# Installing requirements
RUN poetry install --only main

# Removing gcc
RUN apt-get purge -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# Copying actual application
COPY . /app/src/
RUN poetry install --only main

ARG OBJECTIVE_VERSION=1.0.0
ENV OBJECTIVE_VERSION=$OBJECTIVE_VERSION

# Set Python path to include the src directory
ENV PYTHONPATH=/app/src

CMD ["/usr/local/bin/python", "app/main.py"]
