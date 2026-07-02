import boto3
import duckdb
import os

def get_latest_data():
    con = duckdb.connect(f'md:?md_token={os.environ["MD_TOKEN"]}')
    
    s3 = boto3.client('s3')
    bucket = 'config-elt-bucket'
    prefix = 'bronze/'
    
    # 1. List semua folder (prefix) di dalam 'bronze/'
    paginator = s3.get_paginator('list_objects_v2')
    folders = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter='/'):
        for prefix_data in page.get('CommonPrefixes', []):
            folders.add(prefix_data['Prefix'])
    
    # 2. Ambil folder dengan tanggal terbaru (karena formatnya yyyy-mm-dd, string sort works!)
    latest_folder = sorted(list(folders))[-1]
    if not folders:
        raise ValueError("No bronze folders found in S3. Run bronze.py first.")
    latest_path = f"s3://{bucket}/{latest_folder}*.json"
    
    print(f"Membaca data dari: {latest_path}")
    
    # 3. Masukkan ke query DuckDB
    query = f'''
    CREATE OR REPLACE TABLE silver_company_profiles AS
    WITH raw_data AS (
        SELECT * FROM read_json_auto('{latest_path}')
    ),
    raw_extracted AS (
        SELECT 
            lpad(cik::VARCHAR, 10, '0') AS cik,
            name AS company_name,
            list_extract(tickers, 1) AS primary_ticker,
            list_extract(exchanges, 1) AS primary_exchange,
            entityType AS category,
            sicDescription AS industry
        FROM raw_data
    )
    SELECT * FROM raw_extracted
    QUALIFY ROW_NUMBER() OVER (PARTITION BY cik ORDER BY company_name DESC) = 1;
    '''
    con.execute(query)
    data = con.execute("SELECT * FROM silver_company_profiles").fetchdf()
    return data
