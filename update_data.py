import os
import duckdb
import json

def main():
  token = os.environ.get("MD_TOKEN")
  if not token:
    raise ValueError("TOKEN tidak ditemukan dienvironment variables")
  
  con = duckdb.connect(f"md:?motherduck_token={token}")
  
  query = """
  SELECT * 
  FROM "Sec_DB"."main"."gold_company_profiles"
  ORDER BY timestamp DESC;
  """
  
  df = con.sql(query).df()
  os.makedirs("data", exist_ok=True)
  df.to_json("data/metrics.json", orient="records", date_format="iso")
  print("Data berhasil diperbarui dan disimpan ke data/metrics.json")
  
if __name__ == "__main__": 
  main()
