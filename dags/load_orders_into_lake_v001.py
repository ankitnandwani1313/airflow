from airflow import DAG
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable
import csv
import json
import tempfile
import os


dag_file_name = os.path.basename(__file__)       # e.g., load_orders_into_lake_v001.py
dag_id = os.path.splitext(dag_file_name)[0]

data_pipeline_config_str = Variable.get("data_pipeline_config")
data_pipeline_config = json.loads(data_pipeline_config_str)

MYSQL_CONN_ID = data_pipeline_config["mysql_conn_id"]
AWS_CONN_ID = data_pipeline_config["aws_conn_id"]
S3_BUCKET = data_pipeline_config["s3_bucket"]
S3_BASE_DIR = data_pipeline_config["s3_base_dir"]

def extract_table_name(dag_id: str) -> str:
    """Extract table name from DAG ID: load_<table>_into_<target>"""
    try:
        return dag_id.split("load_")[1].split("_into_")[0]
    except Exception:
        raise ValueError(f"DAG ID {dag_id} not in expected format load_<table>_into_<target>")

def extract_and_upload_to_s3(**kwargs):
    dag_id = kwargs["dag"].dag_id
    execution_date = kwargs["execution_date"]
    exec_date_format = execution_date.strftime("%Y%m%d")
    table_name = extract_table_name(dag_id)

    # Connect to MySQL
    mysql_hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID, schema="vibemart")
    conn = mysql_hook.get_conn()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {table_name}")
    columns = [desc[0] for desc in cursor.description]  # only column names, very light

    # Use a temporary file to write CSV row-by-row
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv") as tmpfile:
        writer = csv.writer(tmpfile)
        writer.writerow(columns)  # write header

        rows_written = 0
        while True:
            row = cursor.fetchone()  # fetch one row at a time
            if row is None:
                break
            writer.writerow(row)     # write immediately
            rows_written += 1

        tmpfile_path = tmpfile.name

    cursor.close()
    conn.close()

    # Upload the temp file to S3
    s3_hook = S3Hook(aws_conn_id=AWS_CONN_ID)
    s3_key = f"{S3_BASE_DIR}{table_name}/{exec_date_format}/vibemart_{table_name}_full_load_{exec_date_format}.csv"
    s3_hook.load_file(
        filename=tmpfile_path,
        bucket_name=S3_BUCKET,
        key=s3_key,
        replace=True,
    )
    print(f"✅ Uploaded {rows_written} rows from {table_name} to s3://{S3_BUCKET}/{s3_key}")

# DAG definition
with DAG(
    dag_id=dag_id,   # Example: will extract table 'orders'
    start_date=days_ago(1),
    schedule_interval=None,
    catchup=False,
    tags=["mysql", "s3", "replication"],
) as dag:
    start_task = EmptyOperator(task_id="start")

    load_in_lake = PythonOperator(
        task_id="extract_and_upload_to_s3",
        python_callable=extract_and_upload_to_s3,
        provide_context=True,
    )

    end_task = EmptyOperator(task_id="end")

    start_task >> load_in_lake >> end_task