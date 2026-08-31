import os
import re

def create_safe_wrapper():
    """Membuat modul helper agar Pandas `.rolling()` dapat memproses numpy ndarray secara transparan."""
    patch_code = """import pandas as pd
import numpy as np

# Patch global pada pandas Series/DataFrame rolling agar toleran terhadap ndarray
def patch_pandas_rolling():
    orig_rolling = pd.Series.rolling
    def safe_rolling(self, *args, **kwargs):
        if isinstance(self, np.ndarray):
            self = pd.Series(self)
        return orig_rolling(self, *args, **kwargs)
    pd.Series.rolling = safe_rolling

patch_pandas_rolling()
"""
    with open("patch_rolling_fix.py", "w", encoding="utf-8") as f:
        f.write(patch_code)
    print("[SUCCESS] Membakar patch_rolling_fix.py")

def patch_target_files():
    targets = [
        'indicator_engine.py', 
        'backtest_engine.py', 
        'ea_live_simulator.py', 
        'ea_live_simulator_stage2.py',
        'condition_builder.py',
        'transpiler.py',
        'app.py'
    ]

    for target in targets:
        if not os.path.exists(target):
            continue
        
        with open(target, 'r', encoding='utf-8') as f:
            content = f.read()

        # Inject import helper di paling atas file
        if "import patch_rolling_fix" not in content:
            content = "import patch_rolling_fix\n" + content
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[SUCCESS] Injeksi patch pada {target}")

def main():
    print("=== Patch 4: Global Fix numpy rolling attribute error ===")
    create_safe_wrapper()
    patch_target_files()
    print("=== Selesai ===")

if __name__ == '__main__':
    main()