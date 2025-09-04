FROM apache/airflow:2.8.3

USER root

# Install Java (for PySpark), Kafka library dependencies, and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    openjdk-11-jdk-headless \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt
