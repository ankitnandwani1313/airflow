from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago
import pandas as pd
import numpy as np

# Define the default arguments
default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),  # Adjust this to set the DAG start time
}

# Initialize the DAG
dag = DAG(
    'pandas_numpy_custom_data_dag',
    default_args=default_args,
    description='A simple DAG using Pandas and NumPy with custom data',
    schedule_interval='@daily',  # Runs once every day
)

# Task 1: Create and process custom data using Pandas and NumPy
def process_custom_data(**context):
    # Create a DataFrame with custom data
    data = {
        'id': [1, 2, 3, 4, 5],
        'value': [10, 20, 30, 40, 50],
        'category': ['A', 'B', 'A', 'B', 'A']
    }
    
    df = pd.DataFrame(data)
    print("Original DataFrame:")
    print(df)
    
    # Example Pandas transformation: adding a new column based on existing data
    df['value_squared'] = df['value'] ** 2
    
    # Example NumPy operation: Generating random numbers and adding them to the DataFrame
    df['random_noise'] = df['value'] + np.random.normal(0, 5, len(df))
    
    print("\nProcessed DataFrame:")
    print(df)
    
    # Storing processed data into context (XCom) for the next task
    context['ti'].xcom_push(key='processed_data', value=df.to_dict())

# Task 2: Retrieve the processed data and print a success message
def success_message(**context):
    # Retrieve the processed data from the previous task via XCom
    processed_data = context['ti'].xcom_pull(task_ids='process_custom_data', key='processed_data')
    df_processed = pd.DataFrame(processed_data)
    
    print("\nFinal Data:")
    print(df_processed)
    print("Data processing completed successfully!")

# PythonOperator tasks
task_process_custom_data = PythonOperator(
    task_id='process_custom_data',
    python_callable=process_custom_data,
    provide_context=True,
    dag=dag,
)

task_success_message = PythonOperator(
    task_id='success_message',
    python_callable=success_message,
    provide_context=True,
    dag=dag,
)

# Set the task dependencies
task_process_custom_data >> task_success_message