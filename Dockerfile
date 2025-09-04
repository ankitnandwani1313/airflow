FROM apache/airflow:2.8.3-python3.11

USER airflow

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.3/constraints-3.11.txt" \
       -r /requirements.txt