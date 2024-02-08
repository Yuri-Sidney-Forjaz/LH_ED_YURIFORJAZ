import os
import csv
import psycopg2
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
from psycopg2 import sql
from contextlib import closing

# Define the DAG's default parameters
dag_params = {
    'owner': 'airflow_user',
    'depends_on_past': False,
    'start_date': days_ago(0),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_interval': timedelta(minutes=5),
}

# Initialize the DAG instance
etl_dag = DAG(
    'etl_northwind_traders',
    default_args=dag_params,
    description='Data pipeline for transforming Northwind Traders data',
    schedule_interval=timedelta(days=1),
)

def postgres_data_extraction(**kwargs):
    exec_date = kwargs['ds']
    db_connection_id = 'northwind_postgres'
    postgres_conn = PostgresHook(postgres_conn_id=db_connection_id)
    connection_string = postgres_conn.get_uri()
    data_directory = os.path.join(kwargs['AIRFLOW_HOME'], f"postgres_data/{exec_date}")
    if not os.path.isdir(data_directory):
        os.makedirs(data_directory)

    db_tables = ['categories', 'customers', 'employees', 'orders', 'products', 'shippers', 'suppliers']
    with closing(psycopg2.connect(connection_string)) as connection:
        with connection.cursor() as cursor:
            for table_name in db_tables:
                export_query = sql.SQL("COPY (SELECT * FROM {}) TO STDOUT WITH CSV HEADER").format(sql.Identifier(table_name))
                file_output_path = os.path.join(data_directory, f"{table_name}.csv")
                with open(file_output_path, 'w', newline='') as outfile:
                    cursor.copy_expert(export_query, outfile)

def csv_data_extraction(**kwargs):
    exec_date = kwargs['ds']
    src_file_path = os.path.join(kwargs['AIRFLOW_HOME'], 'data/order_details.csv')
    destination_directory = os.path.join(kwargs['AIRFLOW_HOME'], f"csv_data/{exec_date}")
    if not os.path.isdir(destination_directory):
        os.makedirs(destination_directory)
    dest_file_path = os.path.join(destination_directory, 'order_details_transformed.csv')

    with open(src_file_path, 'r') as src_file, open(dest_file_path, 'w', newline='') as dest_file:
        csv_reader = csv.reader(src_file)
        csv_writer = csv.writer(dest_file)
        for data_row in csv_reader:
            csv_writer.writerow(data_row)

def upload_to_postgres(**kwargs):
    exec_date = kwargs['ds']
    db_conn_id = 'northwind_postgres'
    postgres_conn_hook = PostgresHook(postgres_conn_id=db_conn_id)
    connection = postgres_conn_hook.get_conn()
    
    # Upload data for each specified table
    target_tables = ['categories', 'customers', 'employees', 'orders', 'products', 'shippers', 'suppliers']
    for table_name in target_tables:
        data_file_path = os.path.join(kwargs['AIRFLOW_HOME'], f"postgres_data/{exec_date}/{table_name}.csv")
        with open(data_file_path, 'r') as data_file:
            cursor = connection.cursor()
            cursor.copy_expert(f"COPY {table_name} FROM STDIN WITH CSV HEADER", data_file)
            connection.commit()
            cursor.close()

    # Upload order_details data
    details_path = os.path.join(kwargs['AIRFLOW_HOME'], f"csv_data/{exec_date}/order_details_transformed.csv")
    with open(details_path, 'r') as details_file:
        cursor = connection.cursor()
        cursor.copy_expert(f"COPY order_details FROM STDIN WITH CSV HEADER", details_file)
        connection.commit()
        cursor.close()

    connection.close()

# Defining tasks
extract_from_postgres = PythonOperator(
    task_id='extract_data_postgres',
    python_callable=postgres_data_extraction,
    op_kwargs={'execution_date': '{{ ds }}'},
    dag=etl_dag,
)

extract_from_csv = PythonOperator(
    task_id='extract_data_csv',
    python_callable=csv_data_extraction,
    op_kwargs={'execution_date': '{{ ds }}'},
    dag=etl_dag,
)

load_into_postgres = PythonOperator(
    task_id='upload_data_postgres',
    python_callable=upload_to_postgres,
    op_kwargs={'execution_date': '{{ ds }}'},
    dag=etl_dag,
)

# Setting task dependencies
extract_from_postgres >> extract_from_csv >> load_into_postgres
