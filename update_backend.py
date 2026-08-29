import re

with open("app.py", "r") as f:
    code = f.read()

# Tambahkan fungsi pembaca file bulanan otomatis
new_loader_logic = '''
def get_required_parquet_files(symbol, start_date, end_date, tick_dir):
    """Mengambil daftar file Parquet bulanan yang sesuai rentang tanggal."""
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Generate daftar bulan (YYYYMM)
    ym_list = pd.date_range(start=start_dt, end=end_dt, freq='MS').strftime('%Y%m').tolist()
    
    # Tambahkan bulan akhir jika belum tercover
    end_ym = end_dt.strftime('%Y%m')
    if end_ym not in ym_list:
        ym_list.append(end_ym)
        
    required_files = []
    for ym in ym_list:
        # Format nama file bulanan baru: XAUUSD_MYYYYMM.parquet
        target_file = os.path.join(tick_dir, f"{symbol}_M{ym}.parquet")
        if os.path.exists(target_file):
            required_files.append(target_file)
            
    return required_files
'''

# Sisipkan fungsi jika belum ada di app.py
if "get_required_parquet_files" not in code:
    code = new_loader_logic + "\n" + code
    with open("app.py", "w") as f:
        f.write(code)
    print("✅ Logic pembacaan file Parquet bulanan berhasil disisipkan ke app.py!")
else:
    print("ℹ️ Logic pembacaan file bulanan sudah ada di app.py.")
