# Start from a base image with Python
FROM mcr.microsoft.com/devcontainers/python:3.11

# Install Microsoft ODBC Driver 17 for SQL Server
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Set working directory
WORKDIR /workspaces/app

# Install Python dependencies (optional)
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
