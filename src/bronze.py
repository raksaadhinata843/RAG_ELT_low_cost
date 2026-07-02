import os
import requests
import json
import boto3
import time
from datetime import datetime

# Inisialisasi global untuk reuse
s3_client = boto3.client('s3')
session = requests.Session() 

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

            if len(nasdaq_ciks) >= 10:
                break
               
        return nasdaq_ciks
    except Exception as e:
        print(f"Error di get_all_ciks: {str(e)}")
        return []

def fetch_and_save_to_s3(cik, bucket_name):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = session.get(url, headers=get_sec_headers())
    response.raise_for_status()
    data = response.json()

    company_name = data.get('name') or data.get('entityName', 'Unknown')
    ticker = data.get('tickers', 'UNKNOWN')
    
    file_key = f"bronze/{datetime.now().strftime('%Y-%m-%d')}/sec_data_{ticker}_{cik}.json"
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    return company_name

def handler(event, context):
    raw_cik = event.get('cik')
    mode_auto = (not raw_cik) or (str(raw_cik).lower().strip() == 'auto')
    bucket_name = 'config-elt-bucket'

    # Logic AUTO
    if mode_auto:
        ciks = get_all_ciks()
        if not ciks:
            return {'statusCode': 404, 'body': 'No CIKs found'}
        
        ingested = []
        for cik in ciks[:10]:
            try:
                name = fetch_and_save_to_s3(cik, bucket_name)
                ingested.append(name)
                time.sleep(0.3) # SEC menyarankan delay agar tidak di-block
            except Exception as e:
                print(f"Gagal memproses {cik}: {e}")
        
        return {'statusCode': 200, 'body': json.dumps({'success': ingested})}

    # Logic MANUAL
    else:
        try:
            name = fetch_and_save_to_s3(str(raw_cik).zfill(10), bucket_name)
            return {'statusCode': 200, 'body': json.dumps({'success': name})}
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
