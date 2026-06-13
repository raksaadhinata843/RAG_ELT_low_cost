import os
import requests
import json
import boto3
import time
from datetime import datetime

# Fungsi Helper untuk Header agar konsisten
def get_sec_headers():
    return {
        'User-Agent': f'RaksaProject ({os.environ.get("SEC_EMAIL")})',
        'Accept-Encoding': 'gzip, deflate'
    }

def get_all_ciks():
    # URL ini menggunakan domain www.sec.gov
    ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
    
    try:
        response = requests.get(ticker_url, headers=get_sec_headers())
        response.raise_for_status()
        raw_data = response.json()

        # Gunakan get untuk keamanan
        data_rows = raw_data.get("data", [])
        fields = raw_data.get("fields", [])
        
        cik_idx = fields.index("cik")
        exchange_idx = fields.index("exchange")

        nasdaq_ciks = []
        for row in data_rows:
            # .strip() untuk antisipasi spasi tersembunyi
            if "nasdaq" in str(row[exchange_idx]).strip().lower():
                nasdaq_ciks.append(str(row[cik_idx]).zfill(10))
               
        return nasdaq_ciks
    except Exception as e:
        print(f"Error di get_all_ciks: {str(e)}")
        return []

def fetch_and_save_to_s3(cik, user_email, bucket_name):
    # Data SEC menggunakan domain data.sec.gov
    company_data_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    
    response = requests.get(company_data_url, headers=get_sec_headers())
    response.raise_for_status()
    data = response.json()

    company_name = data.get('name', data.get('entityName', 'Unknown Company'))
    ticker = data.get('ticker', 'UNKNOWN')
    
    s3 = boto3.client('s3')
    file_name = f"bronze/{datetime.now().strftime('%Y-%m-%d')}/sec_data_{ticker}_{cik}.json"
    
    s3.put_object(
        Bucket=bucket_name,
        Key=file_name,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    return company_name

def handler(event, context):
    user_email = os.environ.get('SEC_EMAIL')
    bucket_name = 'config-elt-bucket'
    
    raw_cik = event.get('cik')
    # Jika 'auto' atau None, proses batch
    is_auto = not raw_cik or str(raw_cik).lower() == 'auto'
    
    try:
        if not is_auto:
            # Skenario 1: CIK Spesifik
            cik_padded = str(raw_cik).zfill(10)
            name = fetch_and_save_to_s3(cik_padded, user_email, bucket_name)
            return {'statusCode': 200, 'body': json.dumps({'message': f'Sukses: {name}'})}
        
        else:
            # Skenario 2: Auto Batch
            ciks = get_all_ciks()
            if not ciks:
                raise Exception("Daftar CIK gagal diambil atau kosong.")
                
            start = event.get('start_index', 0)
            target = ciks[start : start + 10]
            
            results = []
            for cik in target:
                results.append(fetch_and_save_to_s3(cik, user_email, bucket_name))
                time.sleep(0.15)
                
            return {'statusCode': 200, 'body': json.dumps({'companies': results})}
            
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
