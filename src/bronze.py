import os
import requests
import json
import boto3
import time

def get_all_ciks():
    ticker_url = "[https://www.sec.gov/files/company_tickers.json](https://www.sec.gov/files/company_tickers.json)"
    headers = {
        'User-Agent': f'RaksaProject ({user_email})',
        'Accept-Encoding': 'gzip, deflate',
        'Host': 'data.sec.gov'
    }
    
    try:
        response = requests.get(ticker_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        ciks_list = []
        for key, value in data.items():
            # Pad CIK menjadi 10 digit string (misal: 320193 -> '0000320193')
            cik_padded = str(value['cik_str']).zfill(10)
            ciks_list.append(cik_padded)
            
            print(f"Ingestion sukses: {data.get('name')}")
        return ciks_list
        
    except Exception as e:
        print(f"Gagal mengambil daftar CIK: {str(e)}")
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

    ticker = data.get('ticker', 'UNKNOWN')
    
    s3 = boto3.client('s3')
    file_name = f"bronze/sec_data_{ticker}_{cik}.json"
    
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
    specific_cik = event.get('cik')

    try:
        if specific_cik:
            # Skenario 1: Hanya proses CIK yang dikirim dari payload CLI
            print(f"Memproses CIK spesifik dari payload: {specific_cik}")
            cik_padded = str(specific_cik).zfill(10)
            company_name = fetch_and_save_to_s3(cik_padded, user_email, bucket_name)
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Sukses ingest data untuk {company_name}'})
            }
        else:
            # Skenario 2: Kalau payload kosong, jalankan otomatis untuk 10 perusahaan pertama
            print("Payload kosong, memproses 10 CIK pertama dari SEC...")
            ciks = get_all_ciks(user_email)
            
            if not ciks:
                raise Exception("Daftar CIK kosong atau gagal diambil.")
                
            target_ciks = ciks[:10]
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
