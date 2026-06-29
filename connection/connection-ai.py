import duckdb
import os
import time
from google import genai
from google.genai import errors

def get_sql_from_ai(client, model_id, prompt):
    """Fungsi pembantu untuk memanggil AI"""
    response = client.models.generate_content(
        model=model_id,
        contents=prompt
    )
    return response.text.strip()

def text_to_sql_chat():
    # 1. Koneksi ke MotherDuck
    md_token = os.environ.get('MD_TOKEN')
    con = duckdb.connect(f'md:?md_token={md_token}')
    
    # 2. Ambil Schema (Hanya nama kolom untuk hemat token & kuota)
    columns = con.execute("SELECT company_name FROM (DESCRIBE silver_company_profiles)").fetchall()
    column_list = [col[0] for col in columns]
    
    # 3. Setup LLM
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print("Mengecek daftar model yang tersedia...")
    for m in client.models.list():
        print(f"ID Model Tersedia: {m.name}")
    
    # List model cadangan (Fallback chain)
    model_pool = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    
    user_question = "Nama perusahaan top 10 yang terdaftar di exchange NASDAQ?"
    prompt = f"""Write a DuckDB SQL query for table 'silver_company_profiles' with columns {column_list}.
    Question: {user_question}. Return ONLY SQL."""

    sql_query = None

    # 4. Looping Fallback & Retry
    for model_id in model_pool:
        print(f"Mencoba model: {model_id}...")
        try:
            sql_query = get_sql_from_ai(client, model_id, prompt)
            if sql_query:
                print(f"Berhasil menggunakan {model_id}")
                break
        except errors.APIError as e:
            if e.code == 429:
                print(f"-> Model {model_id} kena Rate Limit (429).")
            elif e.code == 404:
                print(f"-> Model {model_id} Gak Ditemukan (404).")
            else:
                print(f"-> API Error Lain ({e.code}) pada {model_id}: {e.message}")            
            if model_id != model_pool[-1]:
                print("Beralih ke model cadangan...")
                continue # Coba model berikutnya di list
            else:
                print("Semua model Gemini sibuk. Menunggu 60 detik sebelum menyerah...")
                time.sleep(60)
        except Exception as e:
                print(f"-> Error Non-API pada {model_id}: {e}")
                break

    # 5. Jalankan di MotherDuck jika query berhasil didapat
    if sql_query:
        print(f"Generated SQL: {sql_query}")
        try:
            # Bersihkan backticks jika AI nakal masih menyertakannya
            clean_sql = sql_query.replace('```sql', '').replace('```', '').strip()
            result = con.execute(clean_sql).fetchall()
            print(f"Answer: {result}")
        except Exception as e:
            print(f"SQL Execution Error: {e}")
    else:
        print("Gagal mendapatkan query dari semua model AI.")

if __name__ == "__main__":
    text_to_sql_chat()
