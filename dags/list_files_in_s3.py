from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import boto3
import logging

# DAG default arguments
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 9, 4),
    'retries': 1
}


# Function to list S3 files
def list_s3_files(bucket_name: str, prefix: str = ''):
    """
    List all files in a given S3 bucket and optional prefix.

    :param bucket_name: S3 bucket name
    :param prefix: Optional folder/path inside bucket
    """
    s3_client = boto3.client('s3')
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if 'Contents' in response:
        files = [obj['Key'] for obj in response['Contents']]
        logging.info(f"Files in bucket '{bucket_name}' with prefix '{prefix}': {files}")
    else:
        logging.info(f"No files found in bucket '{bucket_name}' with prefix '{prefix}'")


# Define DAG
with DAG(
        dag_id='list_s3_files',
        default_args=default_args,
        schedule_interval='@daily',
        catchup=False,
        tags=['example', 's3', 'boto3']
) as dag:
    list_files = PythonOperator(
        task_id='list_s3_files_task',
        python_callable=list_s3_files,
        op_kwargs={
            'bucket_name': 'vb-test-dataaquisition-vibemart-com',  # replace with your bucket
            'prefix': 'data-master/retail_db/customers/'  # replace with folder prefix if needed
        }
    )

    list_files
