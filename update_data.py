import os
import duckdb
import json
def main():
# Ambil token dari environment variable
token = os.environ.get("MD_TOKEN")
if not token:
raise ValueError("TOKEN tidak ditemukan dienvironment variables")
# Koneksi ke MotherDuck
# Token dimasukkan ke dalam connection string sa_api_key
con = duckdb.connect(f"md:?motherduck_token={token}")

# Query data dari layer Gold Anda
# Sesuaikan nama database, schema, dan tabel Anda
query = """
SELECT *
FROM "Sec_DB"."main"."gold_company_profiles"
ORDER BY timestamp DESC;
"""
df = con.sql(query).df()
# Buat folder data jika belum ada
os.makedirs("data", exist_ok=True)
# Simpan sebagai JSON statis untuk dikonsumsi frontend
df.to_json("data/metrics.json", orient="records",
date_format="iso")
print("Data berhasil diperbarui dan disimpan ke
data/metrics.json")
if __name__ == "__main__":
main()
