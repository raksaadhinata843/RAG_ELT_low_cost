CREATE OR REPLACE TABLE silver_company_profiles AS
WITH raw_extracted AS (
    SELECT 
        lpad(cik::VARCHAR, 10, '0') AS cik,          -- Casting & Padding CIK
        upper(name) AS company_name,                 -- Normalisasi Nama
        tickers[1]::VARCHAR AS primary_ticker,       -- Ambil ticker pertama
        exchanges[1]::VARCHAR AS primary_exchange,
        sic::INTEGER AS sic_code,                    -- Casting ke Integer
        sicDescription AS industry,
        entityType AS category,
        fiscalYearEnd AS fiscal_year_end
    FROM read_json_auto('s3://config-elt-bucket/bronze/sec_data_*.json')
)
SELECT * 
FROM raw_extracted
-- Membuang duplikasi: Jika ada CIK yang sama, ambil salah satu saja
QUALIFY ROW_NUMBER() OVER (PARTITION BY cik ORDER BY company_name DESC) = 1;
