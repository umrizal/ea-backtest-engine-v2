import os
import re

def patch_file(filepath):
    if not os.path.exists(filepath):
        print(f"[SKIP] File {filepath} tidak ditemukan.")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    
    # 1. Tambahkan helper function jika belum ada
    if "_ensure_series" not in content:
        helper = """
import pandas as pd
import numpy as np

def _ensure_series(val):
    if isinstance(val, np.ndarray):
        return pd.Series(val)
    elif not isinstance(val, (pd.Series, pd.DataFrame)):
        return pd.Series(val)
    return val
"""
        content = helper + "\n" + content

    # 2. Bungkus eksekusi .rolling() dengan _ensure_series()
    content = re.sub(r'(?<!_ensure_series\()([a-zA-Z_][a-zA-Z0-9_]*(\[[^\]]+\])?)\.rolling\(', r'_ensure_series(\1).rolling(', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[SUCCESS] {filepath} berhasil diperbaiki.")
        return True
    else:
        print(f"[INFO] {filepath} sudah valid / tidak memerlukan patch.")
        return False

def main():
    print("=== Patch 3: Fix numpy.ndarray has no attribute 'rolling' ===")
    targets = ['indicator_engine.py', 'backtest_engine.py', 'condition_builder.py', 'transpiler.py']
    
    patched_any = False
    for target in targets:
        if patch_file(target):
            patched_any = True

    if patched_any:
        print("\n[DONE] Seluruh perbaikan selesai diterapkan! Silakan jalankan kembali aplikasi Anda.")
    else:
        print("\n[INFO] Tidak ada file yang diubah.")

if __name__ == '__main__':
    main()