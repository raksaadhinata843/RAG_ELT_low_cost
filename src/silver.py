import boto3
import duckdb

def get_latest_data():
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
    latest_folder = sorted(list(folders))[-1] # Contoh: 'bronze/2026-06-28/'
    latest_path = f"s3://{bucket}/{latest_folder}*.json"
    
    print(f"Membaca data dari: {latest_path}")
    
    # 3. Masukkan ke query DuckDB
    query = f'''
    CREATE OR REPLACE TABLE silver_company_profiles AS
    WITH raw_extracted AS (
        SELECT 
            lpad(cik::VARCHAR, 10, '0') AS cik,
            upper(name) AS company_name,
            list_extract(tickers, 1)::VARCHAR AS primary_ticker,
            list_extract(exchanges, 1)::VARCHAR AS primary_exchange,
            TRY_CAST(sic AS INTEGER) AS sic_code,
            sicDescription AS industry,
            entityType AS category,
            fiscalYearEnd AS fiscal_year_end
        FROM read_json_auto('{latest_path}')
    )
    SELECT * FROM raw_extracted
    QUALIFY ROW_NUMBER() OVER (PARTITION BY cik ORDER BY company_name DESC) = 1;
    '''
    data = duckdb.query(query).to_df()
    return data
