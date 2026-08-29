import re

with open("app.py", "r") as f:
    content = f.read()

# Logic pemuatan file bulanan XAUUSD_MYYYYMM.parquet
loader_patch = '''
def load_ticks_for_range(symbol, start_date, end_date, tick_dir):
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
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
                
                # Standarisasi kolom datetime
                time_col = next((c for c in ['datetime', 'time', 'date', 'timestamp'] if c in df_m.columns), None)
                if time_col:
                    df_m['datetime'] = pd.to_datetime(df_m[time_col], errors='coerce')
                    dfs.append(df_m)
            except Exception as e:
                print(f"Gagal membaca {file_path}: {e}")
                
    if not dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(dfs, ignore_index=True)
    full_df = full_df[(full_df['datetime'] >= start_dt) & (full_df['datetime'] <= end_dt)]
    return full_df.sort_values('datetime').reset_index(drop=True)
'''

if "def load_ticks_for_range" not in content:
    with open("app.py", "w") as f:
        f.write(loader_patch + "\n" + content)
    print("✅ Logic load_ticks_for_range berhasil ditambahkan ke app.py!")
else:
    print("ℹ️ Logic load_ticks_for_range sudah ada.")
