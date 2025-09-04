import os
import csv
import tempfile
import logging
from datetime import timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# ------------------------------
# Load configuration from Airflow Variable
# ------------------------------
data_pipeline_config = Variable.get("data_pipeline_config", deserialize_json=True)
MYSQL_CONN_ID = data_pipeline_config["mysql_conn_id"]
AWS_CONN_ID = data_pipeline_config["aws_conn_id"]
S3_BUCKET = data_pipeline_config["s3_bucket"]
S3_BASE_DIR = data_pipeline_config["s3_base_dir"]
TABLES = data_pipeline_config["tables"]  # list of table names

# ------------------------------
# Dynamic DAG ID from file name
# ------------------------------
dag_file_name = os.path.basename(__file__)
dag_id = os.path.splitext(dag_file_name)[0]

# ------------------------------
# Function to extract and upload table data
# ------------------------------
def extract_and_upload_to_s3(table_name, **kwargs):
    execution_date = kwargs["execution_date"]
    exec_date_format = execution_date.strftime("%Y%m%d")

    try:
        logging.info(f"Starting extraction for table: {table_name}")

        # Connect to MySQL
        mysql_hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID, schema="vibemart")
        conn = mysql_hook.get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cursor.description]

        # Write row-by-row to a temporary CSV
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv") as tmpfile:
            writer = csv.writer(tmpfile)
            writer.writerow(columns)
            rows_written = 0

            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                writer.writerow(row)
                rows_written += 1

            tmpfile_path = tmpfile.name

        cursor.close()
        conn.close()

        # Upload to S3
        s3_key = f"{S3_BASE_DIR}{table_name}/{exec_date_format}/vibermart_{table_name}_full_load_{exec_date_format}.csv"
        s3_hook = S3Hook(aws_conn_id=AWS_CONN_ID)
        s3_hook.load_file(
            filename=tmpfile_path,
            bucket_name=S3_BUCKET,
            key=s3_key,
            replace=True,
        )

        logging.info(f"✅ Successfully uploaded {rows_written} rows from table {table_name} to s3://{S3_BUCKET}/{s3_key}")

    except Exception as e:
        logging.error(f"❌ Error processing table {table_name}: {e}", exc_info=True)
        raise

# ------------------------------
# Define DAG
# ------------------------------
with DAG(
    dag_id=dag_id,
    start_date=days_ago(1),
    schedule_interval=None,
    catchup=False,
    tags=["mysql", "s3", "replication"],
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:

    start_task = EmptyOperator(task_id="start")
    end_task = EmptyOperator(task_id="end")

    # Dynamically create one task per table
    table_tasks = []
    for table_name in TABLES:
        task = PythonOperator(
            task_id=f"extract_and_upload_{table_name}_into_lake",
            python_callable=extract_and_upload_to_s3,
            op_kwargs={"table_name": table_name},
            provide_context=True,
        )
        table_tasks.append(task)

    # Set DAG dependencies: start_task >> all table tasks >> end_task
    start_task >> table_tasks >> end_task