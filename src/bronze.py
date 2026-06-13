import os
import requests
import json
import boto3
import time
from datetime import datetime

def get_all_ciks():
    ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
    user_email = os.environ.get('SEC_EMAIL')
    headers = {
        'User-Agent': f'RaksaProject ({user_email})',
        'Accept-Encoding': 'gzip, deflate',
        'Host': 'data.sec.gov'
    }
    
    try:
        response = requests.get(ticker_url, headers=headers)
        response.raise_for_status()
        raw_data = response.json()

        print(f"DEBUG: Data dari SEC berhasil diambil. Jumlah entri: {len(raw_data.get('data', []))}")

        fields = raw_data["fields"]
        cik_idx = fields.index("cik")
        exchange_idx = fields.index("exchange")

        if "data" not in raw_data:
            raise Exception(f"Struktur data API berubah! Keys: {list(raw_data.keys())}")

        nasdaq_ciks = []
        fields = raw_data["fields"]
        cik_idx = fields.index("cik")
        exchange_idx = fields.index("exchange")

        for row in raw_data["data"]:
            exchange_val = str(row[exchange_idx]).lower()
            if "nasdaq" in exchange_val:
                cik_padded = str(row[cik_idx]).zfill(10)
                nasdaq_ciks.append(cik_padded)
               
        print(f"DEBUG: Total Nasdaq CIKs found: {len(nasdaq_ciks)}")
        return nasdaq_ciks

    except Exception as e:
        print(f"Gagal mengambil daftar CIK Nasdaq: {str(e)}")
        return []

def fetch_and_save_to_s3(cik, user_email, bucket_name):
    """Mengambil data spesifik satu perusahaan dari SEC dan simpan ke S3 Bronze"""
    # SEC menggunakan CIK 10 digit tanpa format string aneh di URL data
    company_data_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    
    headers = {
        'User-Agent': f'RaksaProject ({user_email})',
        'Accept-Encoding': 'gzip, deflate',
        'Host': 'data.sec.gov'
    }
    
    response = requests.get(company_data_url, headers=headers)
    response.raise_for_status()
    data = response.json()

    today = datetime.now().strftime('%Y-%m-%d')
    ticker = data.get('ticker', 'UNKNOWN')
    
    s3 = boto3.client('s3')
    file_name = f"bronze/{today}/sec_data_{ticker}_{cik}.json"
    
    s3.put_object(
        Bucket=bucket_name,
        Key=file_name,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    return data.get('entityName', 'Unknown Company')


def handler(event, context):
    user_email = os.environ.get('SEC_EMAIL')
    bucket_name = 'config-elt-bucket'
    raw_cik = event.get('cik')
    specific_cik = raw_cik if raw_cik and raw_cik.lower() != 'auto' else None
    batch_size = 10
    start_index = event.get('start_index', 0)

    try:
        if specific_cik:
            # Skenario 1: Hanya proses CIK yang dikirim dari payload CLI
            print(f"Memproses CIK spesifik dari payload: {specific_cik}")
            cik_padded = str(specific_cik).zfill(10) 
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Sukses ingest data untuk {company_name}'})
            }
        else:
            # Skenario 2: Kalau payload kosong, jalankan otomatis untuk 10 perusahaan pertama
            print("Payload kosong, memproses 10 CIK pertama dari SEC...")
            ciks = get_all_ciks()
            
            if not ciks:
                raise Exception(f"DEBUG: CIKs list is empty. Logic check needed.")
                
            target_ciks = ciks[start_index : start_index + batch_size]
            ingested_companies = []
            
            for cik in target_ciks:
                company_name = fetch_and_save_to_s3(cik, user_email, bucket_name)
                ingested_companies.append(company_name)
                # SEC punya batasan keras max 10 requests per second (RPS)
                time.sleep(0.15) 
                
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Sukses mengunduh {len(ingested_companies)} perusahaan',
                    'companies': ingested_companies
                })
            }
            
    except Exception as e:
        print(f"Error pada pipeline: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
