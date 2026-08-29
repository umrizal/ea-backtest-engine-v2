import re

with open("app.py", "r") as f:
    code = f.read()

# Logic pemuatan file bulanan XAUUSD_MYYYYMM.parquet secara dinamis
new_loader = '''
def load_ticks_for_range(symbol, start_date, end_date, tick_dir):
    import pandas as pd
    import os
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Ambil rentang bulan YYYYMM
    ym_range = pd.date_range(start=start_dt, end=end_dt, freq='MS').strftime('%Y%m').tolist()
    end_ym = end_dt.strftime('%Y%m')
    if end_ym not in ym_range:
        ym_range.append(end_ym)
        
    dfs = []
    for ym in ym_range:
        file_path = os.path.join(tick_dir, f"{symbol}_M{ym}.parquet")
        if os.path.exists(file_path):
            try:
                df_m = pd.read_parquet(file_path)
                
                # Standarisasi pencarian kolom waktu (datetime, time, date, timestamp)
                time_col = next((c for c in ['datetime', 'time', 'date', 'timestamp'] if c in df_m.columns), None)
                if time_col:
                    df_m['datetime'] = pd.to_datetime(df_m[time_col], errors='coerce')
                    dfs.append(df_m)
            except Exception as e:
                print(f"Error membaca {file_path}: {e}")
                
    if not dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(dfs, ignore_index=True)
    
    # Filter strictly berdasarkan rentang tanggal input UI
    filtered_df = full_df[(full_df['datetime'] >= start_dt) & (full_df['datetime'] <= end_dt)]
    return filtered_df.sort_values('datetime').reset_index(drop=True)
'''

# Tulis perbaikan ke app.py
if "def load_ticks_for_range" not in code:
    with open("app.py", "w") as f:
        f.write(new_loader + "\n" + code)
    print("✅ Logic load_ticks_for_range berhasil disisipkan ke app.py!")
else:
    print("ℹ️ Logic pemuatan file bulanan sudah ada di app.py.")
