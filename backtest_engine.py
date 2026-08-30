# ============================================================
# backtest_engine.py
# Pintarin Laboratorium EA
#
# Universal AI-Driven Backtest Engine
# Support:
#   - CSV
#   - Yearly files: XAUUSD_H1_202601020100_202608280200.csv
#   - OHLC: date,time,open,high,low,close, tickvol, vol, spread
#   - Tick-like data: datetime,bid,ask,last
#
# AI membaca MQL5 -> menghasilkan trading logic
# Engine -> menjalankan simulasi berdasarkan logic tersebut
#
# ============================================================

import os
import glob
import re
import uuid
import math
import traceback

from datetime import datetime

import pandas as pd
import numpy as np

from ai_explainer import AIExplainer
from analytics import QuantitativeAnalytics
from sheet_sync import SheetSyncManager


class BacktestEngine:
    """
    Universal Backtest Engine untuk EA MQL5.

    Arsitektur:

        MQL5 Source
             |
             v
        AIExplainer
             |
             v
        Structured Trading Logic
             |
             v
        Data Broker CSV
             |
             v
        Indicator Engine
             |
             v
        Signal Engine
             |
             v
        Position Simulator
             |
             v
        Quantitative Analytics
             |
             v
        Result / Google Sheet

    Dataset OHLC yang didukung:

        DATE
        TIME
        OPEN
        HIGH
        LOW
        CLOSE
        TICKVOL
        VOL
        SPREAD

    Contoh filename:

        XAUUSD_H1_202601020100_202608280200.csv
    """

    VERSION = "3.0.0"

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        tick_data_dir="data",
        sheet_sync=None,
        ai_explainer=None,
    ):
        self.tick_data_dir = os.path.abspath(tick_data_dir)

        # PERBAIKAN: Gunakan self.tick_data_dir menggantikan folder_path
        os.makedirs(self.tick_data_dir, exist_ok=True)

        self.sheet_sync = (
            sheet_sync
            if sheet_sync is not None
            else SheetSyncManager()
        )

        self.ai_explainer = (
            ai_explainer
            if ai_explainer is not None
            else AIExplainer()
        )

        self._ai_analysis_cache = {}

        # ====================================================
        # STANDARD SYMBOL MAP
        # ====================================================

        self.broker_suffix_map = {
            "XAUUSD": [
                "XAUUSD",
                "XAUUSD.dmb",
                "XAUUSD.pro",
                "XAUUSD.",
                "GOLD",
                "GOLD.dmb",
                "Gold!",
                "XAU",
            ],

            "EURUSD": [
                "EURUSD",
                "EURUSD.dmb",
                "EURUSD.pro",
                "EUR.",
            ],

            "GBPUSD": [
                "GBPUSD",
                "GBPUSD.dmb",
                "GBPUSD.pro",
                "GBP.",
            ],

            "USDJPY": [
                "USDJPY",
                "USDJPY.dmb",
                "USDJPY.pro",
                "JPY.",
            ],

            "AUDUSD": [
                "AUDUSD",
                "AUDUSD.dmb",
                "AUDUSD.pro",
                "AUD.",
            ],

            "USDCAD": [
                "USDCAD",
                "USDCAD.dmb",
                "USDCAD.pro",
                "CAD.",
            ],

            "USDCHF": [
                "USDCHF",
                "USDCHF.dmb",
                "USDCHF.pro",
                "CHF.",
            ],

            "NZDUSD": [
                "NZDUSD",
                "NZDUSD.dmb",
                "NZDUSD.pro",
                "NZD.",
            ],

            "BTCUSD": [
                "BTCUSD",
                "BTCUSD.dmb",
                "BTC",
                "BITCOIN",
            ],

            "ETHUSD": [
                "ETHUSD",
                "ETHUSD.dmb",
                "ETH",
                "ETHEREUM",
            ],

            "US30": [
                "US30",
                "US30.dmb",
                "DJI",
                "DOW",
            ],

            "NAS100": [
                "NAS100",
                "NAS100.dmb",
                "NDX",
            ],

            "SPX500": [
                "SPX500",
                "SPX",
                "US500",
            ],

            "DAX40": [
                "DAX40",
                "DAX",
                "GER40",
            ],
        }

        self.symbol_to_standard = {}

        for standard, variants in self.broker_suffix_map.items():
            for variant in variants:
                self.symbol_to_standard[
                    variant.upper()
                ] = standard

    # ========================================================
    # PROGRESS
    # ========================================================

    def _progress(self, callback, value):
        if callback:
            try:
                callback(int(max(0, min(100, value))))
            except Exception:
                pass

    # ========================================================
    # SYMBOL FUNCTIONS
    # ========================================================

    def _clean_symbol(self, symbol_str):
        """
        XAUUSD.dmb -> XAUUSD
        GOLD -> XAUUSD
        Gold! -> XAUUSD
        """

        if not symbol_str:
            return "XAUUSD"

        cleaned = str(symbol_str).strip()
        upper = cleaned.upper()

        if upper in self.symbol_to_standard:
            return self.symbol_to_standard[upper]

        # Remove broker suffix.
        base = re.split(
            r"[._!]",
            upper
        )[0]

        if base in self.symbol_to_standard:
            return self.symbol_to_standard[base]

        symbol_map = {
            "GOLD": "XAUUSD",
            "XAU": "XAUUSD",

            "BTC": "BTCUSD",
            "BITCOIN": "BTCUSD",

            "ETH": "ETHUSD",
            "ETHEREUM": "ETHUSD",

            "EUR": "EURUSD",
            "GBP": "GBPUSD",

            "US30": "US30",
            "DJI": "US30",
            "DOW": "US30",

            "NAS": "NAS100",
            "NDX": "NAS100",

            "SPX": "SPX500",
            "US500": "SPX500",

            "DAX": "DAX40",
            "GER": "DAX40",
            "GER40": "DAX40",
        }

        return symbol_map.get(
            base,
            base
        )

    def _get_broker_suffix(self, symbol_str):
        if not symbol_str:
            return ""

        symbol = str(symbol_str).strip()

        match = re.search(
            r"([._][a-zA-Z0-9]+)$",
            symbol
        )

        if match:
            return match.group(1)

        if symbol.endswith("!"):
            return "!"

        return ""

    # ========================================================
    # PRICE / POINT FUNCTIONS
    # ========================================================

    def _get_point_size(self, symbol):
        """
        Point size berdasarkan symbol.

        XAUUSD:
            0.01

        Forex:
            0.00001 untuk 5 digit secara default

        JPY:
            0.001

        Index/Crypto:
            1.0

        Catatan:
        Untuk akurasi broker tertentu dapat diberikan melalui params:
            point_size
        """

        s = self._clean_symbol(symbol)

        if s == "XAUUSD":
            return 0.01

        if "JPY" in s:
            return 0.001

        if s in [
            "EURUSD",
            "GBPUSD",
            "AUDUSD",
            "NZDUSD",
            "USDCAD",
            "USDCHF",
        ]:
            return 0.00001

        if s in [
            "US30",
            "NAS100",
            "SPX500",
            "DAX40",
        ]:
            return 1.0

        if s in [
            "BTCUSD",
            "ETHUSD",
        ]:
            return 1.0

        return 0.0001

    def _pip_size(self, symbol):
        s = self._clean_symbol(symbol)

        if s == "XAUUSD":
            return 0.1

        if "JPY" in s:
            return 0.01

        if s in [
            "EURUSD",
            "GBPUSD",
            "AUDUSD",
            "NZDUSD",
            "USDCAD",
            "USDCHF",
        ]:
            return 0.0001

        return 1.0

    def _pip_distance(self, symbol, pips):
        return float(pips) * self._pip_size(symbol)

    # ========================================================
    # CONTRACT VALUE
    # ========================================================

    def _contract_size(self, symbol):
        """
        Contract size approximation.

        XAUUSD:
            100 oz / lot

        Forex:
            100000

        Crypto:
            1

        Index:
            1
        """

        s = self._clean_symbol(symbol)

        if s == "XAUUSD":
            return 100.0

        if s in [
            "EURUSD",
            "GBPUSD",
            "AUDUSD",
            "NZDUSD",
            "USDCAD",
            "USDCHF",
            "USDJPY",
        ]:
            return 100000.0

        if s in [
            "BTCUSD",
            "ETHUSD",
        ]:
            return 1.0

        if s in [
            "US30",
            "NAS100",
            "SPX500",
            "DAX40",
        ]:
            return 1.0

        return 100000.0

    def _calculate_profit(
        self,
        symbol,
        direction,
        entry,
        exit_price,
        lot
    ):
        """
        Approximate P/L.

        BUY:
            (exit - entry) * contract * lot

        SELL:
            (entry - exit) * contract * lot
        """

        contract = self._contract_size(symbol)

        if direction == "BUY":
            return (
                (exit_price - entry)
                * contract
                * lot
            )

        if direction == "SELL":
            return (
                (entry - exit_price)
                * contract
                * lot
            )

        return 0.0

    # ========================================================
    # DATA FILE DISCOVERY
    # ========================================================

    def _candidate_months(
        self,
        start_date,
        end_date
    ):
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        periods = pd.period_range(
            start=start,
            end=end,
            freq="M"
        )

        return [
            p.strftime("%Y%m")
            for p in periods
        ]

    def find_data_files(
        self,
        raw_symbol,
        start_date,
        end_date
    ):
        """
        Mencari SEMUA file monthly yang diperlukan.

        Contoh:

            XAUUSD
            2024-01-01
            2024-12-31

        menghasilkan:

            XAUUSD_H1_202601020100_202608280200.csv
        """

        clean_symbol = self._clean_symbol(
            raw_symbol
        )

        months = self._candidate_months(
            start_date,
            end_date
        )

        files = []

        for ym in months:

            candidates = [
                f"{clean_symbol}_M{ym}.csv",
                f"{raw_symbol}_M{ym}.csv",
            ]

            for filename in candidates:

                path = os.path.join(
                    self.tick_data_dir,
                    filename
                )

                if os.path.exists(path):
                    files.append(path)
                    break

        # Fallback case-insensitive glob.
        if not files:

            for ym in months:

                patterns = [
                    os.path.join(
                        self.tick_data_dir,
                        f"*{clean_symbol}*{ym}*.csv"
                    ),
                ]

                found = []

                for pattern in patterns:
                    found.extend(
                        glob.glob(pattern)
                    )

                if found:
                    files.append(
                        sorted(found)[0]
                    )

        # Fallback terakhir: satu file besar per-symbol yang TIDAK
        # mengikuti pola penamaan bulanan/tahunan sama sekali, mis.
        # export langsung dari MT5:
        #
        #   XAUUSD_H1_202601020100_202608280200.csv
        #
        # File seperti ini berisi seluruh rentang data dalam satu
        # file, jadi cukup dipakai apa adanya lalu difilter per
        # tanggal oleh _filter_by_date().
        if not files:

            single_file_patterns = [
                os.path.join(
                    self.tick_data_dir,
                    f"{clean_symbol}*.csv"
                ),
                os.path.join(
                    self.tick_data_dir,
                    f"*{clean_symbol}*.csv"
                ),
            ]

            found = []

            for pattern in single_file_patterns:
                found.extend(glob.glob(pattern))

            # Case-insensitive: glob di Linux case-sensitive, jadi
            # coba juga pencocokan manual terhadap semua file di
            # folder data (mis. symbol "xauusd" vs file "XAUUSD...").
            if not found and os.path.isdir(self.tick_data_dir):

                for fname in os.listdir(self.tick_data_dir):

                    if not fname.lower().endswith(".csv"):
                        continue

                    if clean_symbol.upper() in fname.upper():
                        found.append(
                            os.path.join(self.tick_data_dir, fname)
                        )

            if found:
                # Ambil semua file yang cocok symbol-nya (biasanya
                # cuma 1 file besar) — jangan dibatasi per-bulan.
                files.extend(sorted(dict.fromkeys(found)))

        return sorted(
            list(dict.fromkeys(files))
        )

    def find_data_file(
        self,
        raw_symbol,
        year
    ):
        """
        Backward-compatible function.

        Mengembalikan file pertama yang ditemukan.
        """

        files = self.find_data_files(
            raw_symbol,
            f"{year}-01-01",
            f"{year}-12-31"
        )

        if files:
            return files[0]

        # Try yearly files.
        clean_symbol = self._clean_symbol(
            raw_symbol
        )

        yearly_candidates = [
            f"{clean_symbol}_{year}.csv",
            f"{raw_symbol}_{year}.csv",
        ]

        for filename in yearly_candidates:

            path = os.path.join(
                self.tick_data_dir,
                filename
            )

            if os.path.exists(path):
                return path

        return None

    # ========================================================
    # DATA LOADING
    # ========================================================

    def load_tick_data(
        self,
        symbol,
        start_date,
        end_date
    ):
        """
        Load broker data.

        Support:

            date + time

        atau:

            datetime

        atau:

            timestamp

        dan:

            open/high/low/close
            bid/ask
            last
        """

        start_dt = pd.to_datetime(
            start_date
        )

        end_dt = pd.to_datetime(
            end_date
        )

        # Jika end_date berupa tanggal tanpa jam,
        # gunakan sampai akhir hari.
        if len(str(end_date)) <= 10:
            end_dt = end_dt + pd.Timedelta(
                days=1
            ) - pd.Timedelta(
                microseconds=1
            )

        files = self.find_data_files(
            symbol,
            start_date,
            end_date
        )

        # Jika monthly tidak ditemukan,
        # coba yearly.
        if not files:

            years = sorted(
                set(
                    pd.date_range(
                        start_dt,
                        end_dt,
                        freq="YS"
                    ).year.tolist()
                )
            )

            for year in years:

                path = self.find_data_file(
                    symbol,
                    str(year)
                )

                if path:
                    files.append(path)

        if not files:
            return pd.DataFrame()

        print(
            f"[DATA] Symbol       : {symbol}"
        )

        print(
            f"[DATA] Clean symbol : "
            f"{self._clean_symbol(symbol)}"
        )

        print(
            f"[DATA] Period       : "
            f"{start_dt} -> {end_dt}"
        )

        print(
            f"[DATA] Files found  : "
            f"{len(files)}"
        )

        dfs = []

        for path in files:

            print(
                f"[DATA] Loading: "
                f"{os.path.basename(path)}"
            )

            try:

                df = self._load_data_file(
                    path
                )

                if df is None or df.empty:
                    continue

                df = self._filter_by_date(
                    df,
                    start_dt,
                    end_dt
                )

                if not df.empty:
                    dfs.append(df)

            except Exception as exc:

                print(
                    f"[DATA] Error loading "
                    f"{path}: {exc}"
                )

        if not dfs:
            return pd.DataFrame()

        full_df = pd.concat(
            dfs,
            ignore_index=True
        )

        if "datetime" in full_df.columns:

            full_df = full_df.sort_values(
                "datetime"
            )

            # Remove duplicate timestamps.
            full_df = full_df.drop_duplicates(
                subset=["datetime"],
                keep="first"
            )

        full_df = (
            full_df
            .reset_index(drop=True)
        )

        print(
            f"[DATA] Total rows loaded: "
            f"{len(full_df):,}"
        )

        return full_df

    # ========================================================
    # FILE READER
    # ========================================================

import os
import pandas as pd
import numpy as np

def load_data(file_path: str) -> pd.DataFrame:
    """
    Membaca file data CSV 9-kolom MetaTrader dan melakukan normalisasi nama kolom
    serta penggabungan kolom <DATE> dan <TIME> menjadi datetime index/column.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File data tidak ditemukan: {file_path}")

    # 1. Deteksi separator (tab atau koma/spasi)
    # File ekspor MetaTrader biasanya menggunakan Tab atau Koma
    try:
        df = pd.read_csv(file_path, sep=r'\s+|\t|,', engine='python')
    except Exception:
        df = pd.read_csv(file_path)

    # 2. Clean nama kolom (hapus < > dan whitespace)
    df.columns = [col.replace('<', '').replace('>', '').strip().lower() for col in df.columns]

    # Mapping nama kolom MetaTrader -> standard engine
    rename_map = {
        'date': 'date',
        'time': 'time',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'tickvol': 'tickvol',
        'vol': 'volume',
        'volume': 'volume',
        'spread': 'spread'
    }
    df = df.rename(columns=rename_map)

    # 3. Gabungkan DATE dan TIME menjadi kolom datetime
    if 'date' in df.columns and 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), errors='coerce')
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'], errors='coerce')

    # Drop baris yang gagal di-parse tanggalnya
    df = df.dropna(subset=['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)

    # 4. Pastikan tipe data numerik untuk harga
    for col in ['open', 'high', 'low', 'close', 'tickvol', 'volume', 'spread']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def parse_filename_info(filename: str) -> dict:
    """
    Ekstrak metadata dari nama file seperti XAUUSD_H1_202601020100_202608280200.csv
    """
    base_name = os.path.basename(filename).replace('.csv', '')
    parts = base_name.split('_')
    
    info = {
        "symbol": parts[0] if len(parts) > 0 else "UNKNOWN",
        "timeframe": parts[1] if len(parts) > 1 else "H1",
        "start_str": parts[2] if len(parts) > 2 else "",
        "end_str": parts[3] if len(parts) > 3 else ""
    }
    return info
    
    # ========================================================
    # STANDARDIZE DATAFRAME
    # ========================================================

    def _standardize_dataframe(
        self,
        df
    ):
        if df is None:
            return None

        df = df.copy()

        # ====================================================
        # TAB-SEPARATED SINGLE COLUMN
        # ====================================================

        if (
            len(df.columns) == 1
            and "\t" in str(df.columns[0])
        ):

            raw_col = df.columns[0]

            columns = [
                c
                .replace("<", "")
                .replace(">", "")
                .strip()
                .lower()
                for c in raw_col.split("\t")
            ]

            df = (
                df[raw_col]
                .astype(str)
                .str.split(
                    "\t",
                    expand=True
                )
            )

            df.columns = columns

        # ====================================================
        # COLUMN NAME NORMALIZATION
        # ====================================================

        rename = {}

        for col in df.columns:

            c = (
                str(col)
                .replace("<", "")
                .replace(">", "")
                .strip()
                .lower()
            )

            c = re.sub(
                r"\s+",
                "_",
                c
            )

            if c in [
                "date",
                "day"
            ]:
                rename[col] = "date"

            elif c in [
                "time",
                "hour",
                "datetime",
                "timestamp",
                "time_msc",
                "datetime_msc"
            ]:
                rename[col] = "time"

            elif c in [
                "bid",
                "bid_price"
            ]:
                rename[col] = "bid"

            elif c in [
                "ask",
                "ask_price"
            ]:
                rename[col] = "ask"

            elif c in [
                "last",
                "last_price"
            ]:
                rename[col] = "last"

            elif c in [
                "open",
                "open_price"
            ]:
                rename[col] = "open"

            elif c in [
                "high",
                "high_price"
            ]:
                rename[col] = "high"

            elif c in [
                "low",
                "low_price"
            ]:
                rename[col] = "low"

            elif c in [
                "close",
                "close_price"
            ]:
                rename[col] = "close"

            elif c in [
                "volume",
                "vol",
                "real_volume"
            ]:
                rename[col] = "volume"

            elif c in [
                "tick_volume",
                "tickvol"
            ]:
                # Simpan terpisah dari "volume" supaya file broker
                # (mis. export MT5) yang punya KEDUA kolom "Tick Volume"
                # dan "Volume" sekaligus tidak bentrok jadi satu nama
                # kolom duplikat (yang akan meledakkan pd.to_numeric).
                rename[col] = "tick_volume"

            elif c in [
                "spread"
            ]:
                rename[col] = "spread"

            else:
                rename[col] = c

        df = df.rename(
            columns=rename
        )

        # Jaga-jaga apabila tetap ada nama kolom duplikat (mis. dua
        # kolom sumber berbeda kebetulan menghasilkan nama yang sama
        # setelah normalisasi) — buang duplikat, pertahankan kolom
        # pertama, supaya df[col] selalu mengembalikan Series (bukan
        # DataFrame) di langkah numeric conversion berikutnya.
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated(keep="first")]

        # ====================================================
        # DATETIME
        # ====================================================

        # Kasus 1:
        # date + time
        if (
            "date" in df.columns
            and "time" in df.columns
        ):

            date_series = (
                df["date"]
                .astype(str)
                .str.strip()
            )

            time_series = (
                df["time"]
                .astype(str)
                .str.strip()
            )

            combined = (
                date_series
                + " "
                + time_series
            )

            parsed = pd.to_datetime(
                combined,
                errors="coerce"
            )

            # Jika time ternyata sudah datetime
            # atau format khusus.
            if parsed.isna().mean() > 0.5:

                parsed = pd.to_datetime(
                    date_series,
                    errors="coerce"
                )

            df["datetime"] = parsed

        # Kasus 2:
        # datetime langsung
        elif "time" in df.columns:

            df["datetime"] = pd.to_datetime(
                df["time"],
                errors="coerce"
            )

        elif "timestamp" in df.columns:

            df["datetime"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce"
            )

        elif "date" in df.columns:

            df["datetime"] = pd.to_datetime(
                df["date"],
                errors="coerce"
            )

        # ====================================================
        # NUMERIC COLUMNS
        # ====================================================

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "bid",
            "ask",
            "last",
            "volume",
            "tick_volume",
            "spread",
        ]

        for col in numeric_columns:

            if col in df.columns:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        # ====================================================
        # DROP INVALID DATETIME
        # ====================================================

        if "datetime" in df.columns:

            df = df[
                df["datetime"].notna()
            ]

        # ====================================================
        # DROP ROW WITHOUT PRICE
        # ====================================================

        price_columns = [
            c
            for c in [
                "open",
                "high",
                "low",
                "close",
                "bid",
                "ask",
                "last",
            ]
            if c in df.columns
        ]

        if price_columns:

            df = df.dropna(
                subset=price_columns,
                how="all"
            )

        return df.reset_index(
            drop=True
        )

    # ========================================================
    # DATE FILTER
    # ========================================================

    def _filter_by_date(
        self,
        df,
        start_dt,
        end_dt
    ):
        if df is None or df.empty:
            return df

        if "datetime" not in df.columns:
            return df

        return df[
            (
                df["datetime"]
                >= start_dt
            )
            &
            (
                df["datetime"]
                <= end_dt
            )
        ].copy()

    # ========================================================
    # PRICE COLUMN
    # ========================================================

    def _detect_price_column(
        self,
        df
    ):
        """
        Untuk OHLC strategy gunakan close.

        Priority:
            close
            last
            bid
            ask
            open
        """

        priority = [
            "close",
            "last",
            "bid",
            "ask",
            "open",
        ]

        for col in priority:

            if (
                col in df.columns
                and df[col].notna().any()
            ):
                return col

        numeric = df.select_dtypes(
            include=np.number
        ).columns

        if len(numeric) > 0:
            return numeric[0]

        return None

    # ========================================================
    # OHLC VALIDATION
    # ========================================================

    def _validate_ohlc(
        self,
        df
    ):
        required = [
            "open",
            "high",
            "low",
            "close",
        ]

        missing = [
            c
            for c in required
            if c not in df.columns
        ]

        return missing

    # ========================================================
    # MQL5 AI ANALYSIS
    # ========================================================

    def _analyze_mql5_code(
        self,
        mql5_code
    ):
        if not mql5_code:
            return self._default_logic()

        code_hash = hash(
            mql5_code
        )

        if (
            code_hash
            in self._ai_analysis_cache
        ):
            return (
                self._ai_analysis_cache[
                    code_hash
                ]
            )

        try:

            # AIExplainer versi baru idealnya
            # menyediakan analyze_structured().
            if hasattr(
                self.ai_explainer,
                "analyze_structured"
            ):

                logic = (
                    self.ai_explainer
                    .analyze_structured(
                        mql5_code
                    )
                )

            else:

                explanation = (
                    self.ai_explainer
                    .explain_ea(
                        mql5_code
                    )
                )

                logic = (
                    self._parse_ai_explanation(
                        explanation,
                        mql5_code
                    )
                )

        except Exception as exc:

            print(
                "[AI] Analysis failed:"
                f" {exc}"
            )

            logic = (
                self._parse_ai_explanation(
                    "",
                    mql5_code
                )
            )

        logic = self._normalize_logic(
            logic
        )

        self._ai_analysis_cache[
            code_hash
        ] = logic

        return logic

    # ========================================================
    # DEFAULT LOGIC
    # ========================================================

    def _default_logic(self):

        return {
            "strategy_type": "ma_crossover",

            "indicators": [
                {
                    "name": "MA",
                    "period": 10
                },
                {
                    "name": "MA",
                    "period": 30
                },
            ],

            "entry_rules": {
                "buy": [
                    "fast MA crosses above slow MA"
                ],
                "sell": [
                    "fast MA crosses below slow MA"
                ],
            },

            "exit_rules": {
                "tp": 50.0,
                "sl": 30.0,
                "tp_unit": "pips",
                "sl_unit": "pips",
                "trailing": 0.0,
                "breakeven": 0.0,
                "opposite_signal": False,
                "time_exit": None,
                "basket_profit": None,
                "basket_loss": None,
            },

            "lot_management": {
                "type": "fixed",
                "base_lot": 0.1,
                "multiplier": 1.0,
                "martingale": False,
                "max_lot": 100.0,
            },

            "risk_management": {
                "max_positions": 1,
                "use_hedging": False,
                "max_spread": None,
                "max_daily_loss": None,
                "max_drawdown": None,
            },

            "time_filters": {
                "enabled": False,
                "start_hour": 0,
                "end_hour": 24,
            },

            "execution": {
                "entry_on_next_bar": False,
                "slippage_points": 0,
                "commission_per_lot": 0,
            },

            "explanation_raw": "",
        }

    # ========================================================
    # PARSE AI EXPLANATION
    # ========================================================

    def _parse_ai_explanation(
        self,
        explanation,
        mql5_code
    ):
        logic = self._default_logic()

        logic[
            "explanation_raw"
        ] = explanation or ""

        text = (
            (explanation or "")
            + "\n"
            + (mql5_code or "")
        ).lower()

        # ====================================================
        # STRATEGY
        # ====================================================

        strategy_patterns = [
            (
                ["moving average", "ma crossover", "ema crossover"],
                "ma_crossover"
            ),
            (
                ["rsi"],
                "rsi"
            ),
            (
                ["macd"],
                "macd"
            ),
            (
                ["bollinger"],
                "bollinger"
            ),
            (
                ["stochastic"],
                "stochastic"
            ),
            (
                ["adx", "directional index"],
                "trend_following"
            ),
            (
                ["grid"],
                "grid"
            ),
            (
                ["martingale"],
                "martingale"
            ),
            (
                ["breakout"],
                "breakout"
            ),
            (
                ["price action"],
                "price_action"
            ),
            (
                ["scalping"],
                "scalping"
            ),
            (
                ["alligator"],
                "alligator"
            ),
            (
                ["fractal"],
                "fractal"
            ),
        ]

        for keywords, strategy in strategy_patterns:

            if any(
                keyword in text
                for keyword in keywords
            ):

                logic[
                    "strategy_type"
                ] = strategy

                break

        # ====================================================
        # INDICATORS
        # ====================================================

        indicator_map = {
            "ima": "Moving Average",
            "ima": "Moving Average",
            "irsi": "RSI",
            "imacd": "MACD",
            "ibands": "Bollinger Bands",
            "istochastic": "Stochastic",
            "iadx": "ADX",
            "iatr": "ATR",
            "icci": "CCI",
            "iwpr": "Williams %R",
            "imomentum": "Momentum",
            "isar": "Parabolic SAR",
            "alligator": "Alligator",
            "fractal": "Fractal",
        }

        detected = []

        for pattern, name in indicator_map.items():

            if pattern in text:
                if name not in detected:
                    detected.append(name)

        if detected:
            logic["indicators"] = detected

        # ====================================================
        # INPUT EXTRACTION
        # ====================================================

        def extract_number(
            names,
            default=None
        ):

            for name in names:

                pattern = (
                    r"(?:input\s+)?"
                    r"(?:double|int|long)?"
                    r"\s*"
                    + re.escape(name)
                    + r"\s*"
                    r"(?:=|:)"
                    r"\s*"
                    r"([-+]?\d*\.?\d+)"
                )

                match = re.search(
                    pattern,
                    mql5_code or "",
                    re.IGNORECASE
                )

                if match:
                    try:
                        return float(
                            match.group(1)
                        )
                    except Exception:
                        pass

            return default

        tp = extract_number(
            [
                "TakeProfit",
                "Take_Profit",
                "TP",
                "TargetProfit",
            ],
            50.0
        )

        sl = extract_number(
            [
                "StopLoss",
                "Stop_Loss",
                "SL",
            ],
            30.0
        )

        trailing = extract_number(
            [
                "TrailingStop",
                "Trailing_Stop",
                "Trailing",
            ],
            0.0
        )

        breakeven = extract_number(
            [
                "BreakEven",
                "Break_Even",
                "BE",
            ],
            0.0
        )

        logic[
            "exit_rules"
        ]["tp"] = tp

        logic[
            "exit_rules"
        ]["sl"] = sl

        logic[
            "exit_rules"
        ]["trailing"] = trailing

        logic[
            "exit_rules"
        ]["breakeven"] = breakeven

        # ====================================================
        # LOT
        # ====================================================

        lot = extract_number(
            [
                "Lot",
                "Lots",
                "BaseLot",
                "InitialLot",
            ],
            0.1
        )

        multiplier = extract_number(
            [
                "LotMultiplier",
                "Lot_Multiplier",
                "Multiplier",
            ],
            1.0
        )

        logic[
            "lot_management"
        ]["base_lot"] = lot

        logic[
            "lot_management"
        ]["multiplier"] = multiplier

        if multiplier > 1:
            logic[
                "lot_management"
            ]["martingale"] = True

            logic[
                "lot_management"
            ]["type"] = "martingale"

        # ====================================================
        # MAX POSITION
        # ====================================================

        max_pos = extract_number(
            [
                "MaxPositions",
                "MaxPosition",
                "MaximumPositions",
                "MaxOrders",
            ],
            1
        )

        logic[
            "risk_management"
        ]["max_positions"] = int(
            max_pos
        )

        # ====================================================
        # FAST / SLOW MA
        # ====================================================

        fast_ma = extract_number(
            [
                "FastMA",
                "Fast_MA",
                "FastPeriod",
            ],
            10
        )

        slow_ma = extract_number(
            [
                "SlowMA",
                "Slow_MA",
                "SlowPeriod",
            ],
            30
        )

        logic[
            "parameters"
        ] = {
            "fast_ma": int(fast_ma),
            "slow_ma": int(slow_ma),
        }

        # ====================================================
        # RSI
        # ====================================================

        rsi_period = extract_number(
            ["RSIPeriod", "RSI_Period"],
            14
        )

        rsi_oversold = extract_number(
            [
                "RSIOversold",
                "RSI_Oversold",
                "Oversold",
            ],
            30
        )

        rsi_overbought = extract_number(
            [
                "RSIOverbought",
                "RSI_Overbought",
                "Overbought",
            ],
            70
        )

        logic[
            "parameters"
        ].update({
            "rsi_period": int(rsi_period),
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought,
        })

        # ====================================================
        # DETECT OPPOSITE SIGNAL
        # ====================================================

        if (
            "opposite signal" in text
            or "reverse signal" in text
            or "close opposite" in text
            or "reverseposition" in text
        ):

            logic[
                "exit_rules"
            ]["opposite_signal"] = True

        # ====================================================
        # GRID
        # ====================================================

        if "grid" in text:

            logic[
                "strategy_type"
            ] = "grid"

            logic[
                "risk_management"
            ]["max_positions"] = max(
                logic[
                    "risk_management"
                ]["max_positions"],
                5
            )

        return logic

    # ========================================================
    # NORMALIZE LOGIC
    # ========================================================

    def _normalize_logic(
        self,
        logic
    ):
        base = self._default_logic()

        if not isinstance(
            logic,
            dict
        ):
            return base

        # Recursive-ish shallow merge.
        for key, value in logic.items():

            if (
                key in base
                and isinstance(
                    base[key],
                    dict
                )
                and isinstance(
                    value,
                    dict
                )
            ):

                base[key].update(value)

            else:

                base[key] = value

        return base

    # ========================================================
    # INDICATOR CALCULATIONS
    # ========================================================

    def _calculate_indicators(
        self,
        df,
        logic
    ):
        data = df.copy()

        close = data["close"].astype(
            float
        )

        params = logic.get(
            "parameters",
            {}
        )

        # ====================================================
        # MA
        # ====================================================

        fast_period = int(
            params.get(
                "fast_ma",
                10
            )
        )

        slow_period = int(
            params.get(
                "slow_ma",
                30
            )
        )

        data["ma_fast"] = (
            close
            .rolling(
                fast_period
            )
            .mean()
        )

        data["ma_slow"] = (
            close
            .rolling(
                slow_period
            )
            .mean()
        )

        data["ema_fast"] = (
            close
            .ewm(
                span=fast_period,
                adjust=False
            )
            .mean()
        )

        data["ema_slow"] = (
            close
            .ewm(
                span=slow_period,
                adjust=False
            )
            .mean()
        )

        # ====================================================
        # RSI
        # ====================================================

        rsi_period = int(
            params.get(
                "rsi_period",
                14
            )
        )

        delta = close.diff()

        gain = (
            delta
            .clip(lower=0)
            .rolling(
                rsi_period
            )
            .mean()
        )

        loss = (
            -delta
            .clip(upper=0)
            .rolling(
                rsi_period
            )
            .mean()
        )

        rs = gain / loss.replace(
            0,
            np.nan
        )

        data["rsi"] = (
            100
            - (
                100
                / (1 + rs)
            )
        )

        # ====================================================
        # MACD
        # ====================================================

        ema12 = close.ewm(
            span=12,
            adjust=False
        ).mean()

        ema26 = close.ewm(
            span=26,
            adjust=False
        ).mean()

        data["macd"] = (
            ema12 - ema26
        )

        data["macd_signal"] = (
            data["macd"]
            .ewm(
                span=9,
                adjust=False
            )
            .mean()
        )

        data["macd_hist"] = (
            data["macd"]
            - data["macd_signal"]
        )

        # ====================================================
        # BOLLINGER
        # ====================================================

        bb_period = int(
            params.get(
                "bb_period",
                20
            )
        )

        bb_std = float(
            params.get(
                "bb_std",
                2.0
            )
        )

        bb_mid = (
            close
            .rolling(
                bb_period
            )
            .mean()
        )

        bb_sigma = (
            close
            .rolling(
                bb_period
            )
            .std()
        )

        data["bb_middle"] = bb_mid

        data["bb_upper"] = (
            bb_mid
            + bb_std * bb_sigma
        )

        data["bb_lower"] = (
            bb_mid
            - bb_std * bb_sigma
        )

        # ====================================================
        # ATR
        # ====================================================

        prev_close = close.shift(1)

        tr1 = (
            data["high"]
            - data["low"]
        )

        tr2 = (
            data["high"]
            - prev_close
        ).abs()

        tr3 = (
            data["low"]
            - prev_close
        ).abs()

        true_range = pd.concat(
            [
                tr1,
                tr2,
                tr3
            ],
            axis=1
        ).max(axis=1)

        data["atr"] = (
            true_range
            .rolling(14)
            .mean()
        )

        # ====================================================
        # STOCHASTIC
        # ====================================================

        stoch_period = int(
            params.get(
                "stochastic_period",
                14
            )
        )

        lowest = (
            data["low"]
            .rolling(
                stoch_period
            )
            .min()
        )

        highest = (
            data["high"]
            .rolling(
                stoch_period
            )
            .max()
        )

        denominator = (
            highest - lowest
        ).replace(
            0,
            np.nan
        )

        data["stoch_k"] = (
            100
            * (
                (close - lowest)
                / denominator
            )
        )

        data["stoch_d"] = (
            data["stoch_k"]
            .rolling(3)
            .mean()
        )

        return data

    # ========================================================
    # SIGNAL ENGINE
    # ========================================================

    def _generate_signals(
        self,
        df,
        logic
    ):
        """
        Menghasilkan signal vector.

        Signal:
            1  = BUY
           -1  = SELL
            0  = NONE
        """

        n = len(df)

        signals = np.zeros(
            n,
            dtype=np.int8
        )

        strategy = str(
            logic.get(
                "strategy_type",
                "unknown"
            )
        ).lower()

        params = logic.get(
            "parameters",
            {}
        )

        close = df[
            "close"
        ].to_numpy(
            dtype=float
        )

        # ====================================================
        # MA CROSSOVER
        # ====================================================

        if strategy in [
            "ma_crossover",
            "trend_following",
            "scalping",
        ]:

            fast = df[
                "ma_fast"
            ].to_numpy()

            slow = df[
                "ma_slow"
            ].to_numpy()

            for i in range(1, n):

                if (
                    np.isnan(fast[i])
                    or np.isnan(slow[i])
                    or np.isnan(fast[i - 1])
                    or np.isnan(slow[i - 1])
                ):
                    continue

                if (
                    fast[i - 1]
                    <= slow[i - 1]
                    and
                    fast[i]
                    > slow[i]
                ):

                    signals[i] = 1

                elif (
                    fast[i - 1]
                    >= slow[i - 1]
                    and
                    fast[i]
                    < slow[i]
                ):

                    signals[i] = -1

        # ====================================================
        # RSI
        # ====================================================

        elif strategy == "rsi":

            rsi = df[
                "rsi"
            ].to_numpy()

            oversold = float(
                params.get(
                    "rsi_oversold",
                    30
                )
            )

            overbought = float(
                params.get(
                    "rsi_overbought",
                    70
                )
            )

            for i in range(1, n):

                if (
                    np.isnan(rsi[i])
                    or np.isnan(rsi[i - 1])
                ):
                    continue

                if (
                    rsi[i - 1]
                    < oversold
                    and
                    rsi[i]
                    >= oversold
                ):

                    signals[i] = 1

                elif (
                    rsi[i - 1]
                    > overbought
                    and
                    rsi[i]
                    <= overbought
                ):

                    signals[i] = -1

        # ====================================================
        # MACD
        # ====================================================

        elif strategy == "macd":

            macd = df[
                "macd"
            ].to_numpy()

            signal = df[
                "macd_signal"
            ].to_numpy()

            for i in range(1, n):

                if (
                    np.isnan(macd[i])
                    or np.isnan(signal[i])
                    or np.isnan(macd[i - 1])
                    or np.isnan(signal[i - 1])
                ):
                    continue

                if (
                    macd[i - 1]
                    <= signal[i - 1]
                    and
                    macd[i]
                    > signal[i]
                ):

                    signals[i] = 1

                elif (
                    macd[i - 1]
                    >= signal[i - 1]
                    and
                    macd[i]
                    < signal[i]
                ):

                    signals[i] = -1

        # ====================================================
        # BOLLINGER
        # ====================================================

        elif strategy == "bollinger":

            upper = df[
                "bb_upper"
            ].to_numpy()

            lower = df[
                "bb_lower"
            ].to_numpy()

            for i in range(n):

                if (
                    np.isnan(upper[i])
                    or np.isnan(lower[i])
                ):
                    continue

                if close[i] <= lower[i]:
                    signals[i] = 1

                elif close[i] >= upper[i]:
                    signals[i] = -1

        # ====================================================
        # BREAKOUT
        # ====================================================

        elif strategy in [
            "breakout",
            "price_action",
        ]:

            lookback = int(
                params.get(
                    "breakout_lookback",
                    20
                )
            )

            for i in range(
                lookback,
                n
            ):

                highest = np.max(
                    df[
                        "high"
                    ].iloc[
                        i - lookback:i
                    ]
                )

                lowest = np.min(
                    df[
                        "low"
                    ].iloc[
                        i - lookback:i
                    ]
                )

                if close[i] > highest:
                    signals[i] = 1

                elif close[i] < lowest:
                    signals[i] = -1

        # ====================================================
        # STOCHASTIC
        # ====================================================

        elif strategy == "stochastic":

            k = df[
                "stoch_k"
            ].to_numpy()

            d = df[
                "stoch_d"
            ].to_numpy()

            for i in range(1, n):

                if (
                    np.isnan(k[i])
                    or np.isnan(d[i])
                    or np.isnan(k[i - 1])
                    or np.isnan(d[i - 1])
                ):
                    continue

                if (
                    k[i - 1]
                    <= d[i - 1]
                    and
                    k[i]
                    > d[i]
                    and
                    k[i] < 30
                ):

                    signals[i] = 1

                elif (
                    k[i - 1]
                    >= d[i - 1]
                    and
                    k[i]
                    < d[i]
                    and
                    k[i] > 70
                ):

                    signals[i] = -1

        # ====================================================
        # GRID
        # ====================================================

        elif strategy in [
            "grid",
            "martingale",
        ]:

            # Grid membutuhkan aturan layer
            # dari AI.
            #
            # Initial direction:
            # MA crossover sebagai directional filter.

            fast = df[
                "ma_fast"
            ].to_numpy()

            slow = df[
                "ma_slow"
            ].to_numpy()

            for i in range(1, n):

                if (
                    np.isnan(fast[i])
                    or np.isnan(slow[i])
                ):
                    continue

                if fast[i] > slow[i]:
                    signals[i] = 1

                elif fast[i] < slow[i]:
                    signals[i] = -1

        # ====================================================
        # ALLIGATOR
        # ====================================================

        elif strategy == "alligator":

            jaw = (
                close
                .rolling(13)
                .mean()
            )

            teeth = (
                close
                .rolling(8)
                .mean()
            )

            lips = (
                close
                .rolling(5)
                .mean()
            )

            for i in range(1, n):

                if any(
                    np.isnan(x)
                    for x in [
                        jaw.iloc[i],
                        teeth.iloc[i],
                        lips.iloc[i],
                        jaw.iloc[i - 1],
                        teeth.iloc[i - 1],
                        lips.iloc[i - 1],
                    ]
                ):
                    continue

                if (
                    lips.iloc[i]
                    > teeth.iloc[i]
                    > jaw.iloc[i]
                    and
                    not (
                        lips.iloc[i - 1]
                        > teeth.iloc[i - 1]
                        > jaw.iloc[i - 1]
                    )
                ):

                    signals[i] = 1

                elif (
                    lips.iloc[i]
                    < teeth.iloc[i]
                    < jaw.iloc[i]
                    and
                    not (
                        lips.iloc[i - 1]
                        < teeth.iloc[i - 1]
                        < jaw.iloc[i - 1]
                    )
                ):

                    signals[i] = -1

        # ====================================================
        # DEFAULT
        # ====================================================

        else:

            fast = df[
                "ma_fast"
            ].to_numpy()

            slow = df[
                "ma_slow"
            ].to_numpy()

            for i in range(1, n):

                if (
                    np.isnan(fast[i])
                    or np.isnan(slow[i])
                    or np.isnan(fast[i - 1])
                    or np.isnan(slow[i - 1])
                ):
                    continue

                if (
                    fast[i - 1]
                    <= slow[i - 1]
                    and
                    fast[i]
                    > slow[i]
                ):

                    signals[i] = 1

                elif (
                    fast[i - 1]
                    >= slow[i - 1]
                    and
                    fast[i]
                    < slow[i]
                ):

                    signals[i] = -1

        return signals

    # ========================================================
    # TIME FILTER
    # ========================================================

    def _time_allowed(
        self,
        timestamp,
        logic
    ):

        time_filter = logic.get(
            "time_filters",
            {}
        )

        if not time_filter.get(
            "enabled",
            False
        ):
            return True

        try:

            hour = timestamp.hour

        except Exception:

            return True

        start = int(
            time_filter.get(
                "start_hour",
                0
            )
        )

        end = int(
            time_filter.get(
                "end_hour",
                24
            )
        )

        if start <= end:
            return start <= hour < end

        # Overnight session.
        return (
            hour >= start
            or hour < end
        )

    # ========================================================
    # SPREAD
    # ========================================================

    def _spread_allowed(
        self,
        row,
        logic,
        symbol
    ):

        max_spread = (
            logic
            .get(
                "risk_management",
                {}
            )
            .get(
                "max_spread",
                None
            )
        )

        if max_spread is None:
            return True

        if (
            "bid" not in row
            or "ask" not in row
        ):
            return True

        spread = (
            float(row["ask"])
            - float(row["bid"])
        )

        max_distance = (
            self._pip_distance(
                symbol,
                max_spread
            )
        )

        return spread <= max_distance

    # ========================================================
    # EXECUTION PRICE
    # ========================================================

    def _entry_price(
        self,
        row,
        direction,
        fallback
    ):

        if direction == "BUY":

            if (
                "ask" in row
                and pd.notna(row["ask"])
            ):
                return float(
                    row["ask"]
                )

        elif direction == "SELL":

            if (
                "bid" in row
                and pd.notna(row["bid"])
            ):
                return float(
                    row["bid"]
                )

        return float(fallback)

    def _exit_price(
        self,
        row,
        direction,
        fallback
    ):

        if direction == "BUY":

            if (
                "bid" in row
                and pd.notna(row["bid"])
            ):
                return float(
                    row["bid"]
                )

        elif direction == "SELL":

            if (
                "ask" in row
                and pd.notna(row["ask"])
            ):
                return float(
                    row["ask"]
                )

        return float(fallback)

    # ========================================================
    # POSITION MANAGEMENT
    # ========================================================

    def _create_position(
        self,
        symbol,
        direction,
        price,
        timestamp,
        lot,
        risk_params
    ):

        tp = risk_params.get(
            "tp",
            0
        )

        sl = risk_params.get(
            "sl",
            0
        )

        tp_distance = (
            self._pip_distance(
                symbol,
                tp
            )
            if tp
            else 0
        )

        sl_distance = (
            self._pip_distance(
                symbol,
                sl
            )
            if sl
            else 0
        )

        position = {
            "order_id": str(
                uuid.uuid4()
            )[:8],

            "direction": direction,

            "arah": direction,

            "entry": float(price),

            "harga_entry": float(price),

            "open_time": str(
                timestamp
            ),

            "lot": float(lot),

            "tp": None,

            "sl": None,

            "highest_price": float(price),

            "lowest_price": float(price),

            "be_activated": False,

            "trailing": 0.0,
        }

        if direction == "BUY":

            if tp_distance > 0:
                position["tp"] = (
                    price
                    + tp_distance
                )

            if sl_distance > 0:
                position["sl"] = (
                    price
                    - sl_distance
                )

        else:

            if tp_distance > 0:
                position["tp"] = (
                    price
                    - tp_distance
                )

            if sl_distance > 0:
                position["sl"] = (
                    price
                    + sl_distance
                )

        return position

    # ========================================================
    # CANDLE EXIT SIMULATION
    # ========================================================

    def _check_position_exit(
        self,
        position,
        row,
        symbol,
        risk_params
    ):
        """
        Simulasi exit menggunakan OHLC.

        Conservative rule:

        BUY:
            cek SL dahulu apabila low <= SL
            kemudian TP.

        SELL:
            cek SL dahulu apabila high >= SL
            kemudian TP.

        Ini sengaja konservatif ketika satu candle
        menyentuh TP dan SL sekaligus.
        """

        direction = position[
            "direction"
        ]

        high = float(
            row["high"]
        )

        low = float(
            row["low"]
        )

        close = float(
            row["close"]
        )

        exit_price = None
        reason = None

        # ====================================================
        # UPDATE EXTREME
        # ====================================================

        if direction == "BUY":

            position[
                "highest_price"
            ] = max(
                position[
                    "highest_price"
                ],
                high
            )

        else:

            position[
                "lowest_price"
            ] = min(
                position[
                    "lowest_price"
                ],
                low
            )

        # ====================================================
        # BREAK EVEN
        # ====================================================

        be = float(
            risk_params.get(
                "breakeven",
                0
            ) or 0
        )

        if (
            be > 0
            and not position[
                "be_activated"
            ]
        ):

            distance = (
                self._pip_distance(
                    symbol,
                    be
                )
            )

            if direction == "BUY":

                if high >= (
                    position["entry"]
                    + distance
                ):

                    position[
                        "be_activated"
                    ] = True

                    position["sl"] = (
                        position["entry"]
                    )

            else:

                if low <= (
                    position["entry"]
                    - distance
                ):

                    position[
                        "be_activated"
                    ] = True

                    position["sl"] = (
                        position["entry"]
                    )

        # ====================================================
        # TRAILING STOP
        # ====================================================

        trailing = float(
            risk_params.get(
                "trailing",
                0
            ) or 0
        )

        if trailing > 0:

            distance = (
                self._pip_distance(
                    symbol,
                    trailing
                )
            )

            if direction == "BUY":

                trailing_sl = (
                    position[
                        "highest_price"
                    ]
                    - distance
                )

                if (
                    position["sl"]
                    is None
                    or
                    trailing_sl
                    > position["sl"]
                ):

                    position["sl"] = (
                        trailing_sl
                    )

            else:

                trailing_sl = (
                    position[
                        "lowest_price"
                    ]
                    + distance
                )

                if (
                    position["sl"]
                    is None
                    or
                    trailing_sl
                    < position["sl"]
                ):

                    position["sl"] = (
                        trailing_sl
                    )

        # ====================================================
        # STOP LOSS
        # ====================================================

        if direction == "BUY":

            if (
                position["sl"]
                is not None
                and low
                <= position["sl"]
            ):

                exit_price = (
                    position["sl"]
                )

                reason = (
                    "Stop Loss"
                )

        else:

            if (
                position["sl"]
                is not None
                and high
                >= position["sl"]
            ):

                exit_price = (
                    position["sl"]
                )

                reason = (
                    "Stop Loss"
                )

        if exit_price is not None:

            return (
                True,
                float(exit_price),
                reason
            )

        # ====================================================
        # TAKE PROFIT
        # ====================================================

        if direction == "BUY":

            if (
                position["tp"]
                is not None
                and high
                >= position["tp"]
            ):

                return (
                    True,
                    float(position["tp"]),
                    "Take Profit"
                )

        else:

            if (
                position["tp"]
                is not None
                and low
                <= position["tp"]
            ):

                return (
                    True,
                    float(position["tp"]),
                    "Take Profit"
                )

        return (
            False,
            None,
            None
        )

    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def _close_position(
        self,
        position,
        exit_price,
        timestamp,
        symbol,
        reason,
        balance,
        params,
    ):

        profit = self._calculate_profit(
            symbol,
            position["direction"],
            position["entry"],
            exit_price,
            position["lot"]
        )

        commission = float(
            params.get(
                "commission_per_lot",
                0
            )
        )

        commission_total = (
            commission
            * position["lot"]
        )

        profit -= commission_total

        new_balance = (
            balance
            + profit
        )

        trade = {
            "ea_name": params.get(
                "ea_name",
                "EA_MQL5"
            ),

            "order_id": position[
                "order_id"
            ],

            "arah": position[
                "direction"
            ],

            "direction": position[
                "direction"
            ],

            "harga_entry": round(
                position["entry"],
                8
            ),

            "entry_price": round(
                position["entry"],
                8
            ),

            "open_time": position[
                "open_time"
            ],

            "close_time": str(
                timestamp
            ),

            "close_price": round(
                exit_price,
                8
            ),

            "profit": round(
                profit,
                2
            ),

            "commission": round(
                commission_total,
                2
            ),

            "lot": position[
                "lot"
            ],

            "symbol": params.get(
                "symbol",
                symbol
            ),

            "symbol_clean": symbol,

            "balance": round(
                new_balance,
                2
            ),

            "status": "closed",

            "comment": reason,

            "strategy": params.get(
                "strategy",
                ""
            ),
        }

        return new_balance, trade

    # ========================================================
    # MAIN RUN
    # ========================================================

    def run(
        self,
        params,
        progress_callback=None
    ):
        """
        Main backtest.

        params contoh:

        {
            "ea_name": "TrendGridEA",
            "symbol": "XAUUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "balance": 10000,
            "lot": 0.1,
            "mql5_code": "..."
        }
        """

        started_at = datetime.utcnow()

        raw_symbol = params.get(
            "symbol",
            "XAUUSD"
        )

        symbol_clean = (
            self._clean_symbol(
                raw_symbol
            )
        )

        year = str(
            params.get(
                "year",
                "2024"
            )
        )

        start_date = params.get(
            "start_date",
            f"{year}-01-01"
        )

        end_date = params.get(
            "end_date",
            f"{year}-12-31"
        )

        initial_balance = float(
            params.get(
                "balance",
                10000.0
            )
        )

        base_lot = float(
            params.get(
                "lot",
                0.1
            )
        )

        mql5_code = params.get(
            "mql5_code",
            ""
        )

        # ====================================================
        # START
        # ====================================================

        print(
            "\n"
            "==================================================\n"
            "PINTARIN LABORATORIUM EA\n"
            "BACKTEST ENGINE "
            f"v{self.VERSION}\n"
            "=================================================="
        )

        print(
            f"EA      : "
            f"{params.get('ea_name', 'EA_MQL5')}"
        )

        print(
            f"Symbol  : {raw_symbol}"
        )

        print(
            f"Period  : "
            f"{start_date} -> {end_date}"
        )

        self._progress(
            progress_callback,
            5
        )

        # ====================================================
        # AI ANALYSIS
        # ====================================================

        print(
            "[1/5] Analyzing EA with AI..."
        )

        trading_logic = (
            self._analyze_mql5_code(
                mql5_code
            )
        )

        self._progress(
            progress_callback,
            15
        )

        print(
            "[AI] Strategy: "
            f"{trading_logic.get('strategy_type')}"
        )

        print(
            "[AI] Indicators: "
            f"{trading_logic.get('indicators')}"
        )

        # ====================================================
        # DATA
        # ====================================================

        print(
            "[2/5] Loading broker data..."
        )

        files = self.find_data_files(
            raw_symbol,
            start_date,
            end_date
        )

        if not files:

            raise FileNotFoundError(
                "\n"
                f"Tidak ada data broker untuk "
                f"{raw_symbol} periode "
                f"{start_date} - {end_date}\n\n"
                f"Folder data: "
                f"{self.tick_data_dir}\n\n"
                "File yang diharapkan contoh:\n"
                "XAUUSD_H1_202601020100_202608280200.csv\n"
                "...\n"
                "XAUUSD_H1_202601020100_202608280200.csv"
            )

        print(
            "[DATA] Matching files:"
        )

        for f in files:
            print(
                "  - "
                + os.path.basename(f)
            )

        df = self.load_tick_data(
            raw_symbol,
            start_date,
            end_date
        )

        if df.empty:

            raise FileNotFoundError(
                "\n"
                f"File csv ditemukan tetapi "
                f"tidak ada baris data untuk "
                f"periode {start_date} - "
                f"{end_date}."
            )

        self._progress(
            progress_callback,
            25
        )

        # ====================================================
        # VALIDATE
        # ====================================================

        missing = (
            self._validate_ohlc(df)
        )

        if missing:

            raise ValueError(
                "Kolom OHLC tidak lengkap. "
                f"Missing: {missing}. "
                f"Columns: "
                f"{list(df.columns)}"
            )

        if "datetime" not in df.columns:

            raise ValueError(
                "Kolom datetime gagal dibentuk "
                "dari date + time."
            )

        # ====================================================
        # CLEAN
        # ====================================================

        df = df.replace(
            [np.inf, -np.inf],
            np.nan
        )

        df = df.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
                "datetime",
            ]
        )

        df = df.sort_values(
            "datetime"
        )

        df = df.reset_index(
            drop=True
        )

        # ====================================================
        # RAM SAFETY
        # ====================================================

        max_rows = int(
            params.get(
                "max_rows",
                0
            )
        )

        if (
            max_rows > 0
            and len(df) > max_rows
        ):

            print(
                "[RAM] Limiting rows "
                f"to {max_rows:,}"
            )

            df = df.iloc[
                -max_rows:
            ].reset_index(
                drop=True
            )

        print(
            "[DATA] Final rows: "
            f"{len(df):,}"
        )

        self._progress(
            progress_callback,
            35
        )

        # ====================================================
        # INDICATORS
        # ====================================================

        print(
            "[3/5] Calculating indicators..."
        )

        df = self._calculate_indicators(
            df,
            trading_logic
        )

        signals = (
            self._generate_signals(
                df,
                trading_logic
            )
        )

        df["_signal"] = signals

        self._progress(
            progress_callback,
            45
        )

        # ====================================================
        # SIMULATION
        # ====================================================

        print(
            "[4/5] Running simulation..."
        )

        risk_params = (
            trading_logic.get(
                "exit_rules",
                {}
            )
        )

        lot_management = (
            trading_logic.get(
                "lot_management",
                {}
            )
        )

        risk_management = (
            trading_logic.get(
                "risk_management",
                {}
            )
        )

        max_positions = int(
            risk_management.get(
                "max_positions",
                1
            )
        )

        # ====================================================
        # IMPORTANT:
        # Untuk versi single-position:
        # max_positions tetap dihormati.
        #
        # Untuk grid:
        # multi-position sederhana didukung.
        # ====================================================

        is_grid = (
            trading_logic.get(
                "strategy_type"
            )
            in [
                "grid",
                "martingale",
            ]
        )

        if not is_grid:
            max_positions = 1

        balance = (
            initial_balance
        )

        equity = (
            initial_balance
        )

        current_lot = (
            base_lot
        )

        positions = []

        trades = []

        equity_curve = []

        max_equity = (
            initial_balance
        )

        max_drawdown = 0.0

        total_rows = len(df)

        # ====================================================
        # SIMULATION LOOP
        # ====================================================

        for i in range(
            total_rows
        ):

            row = df.iloc[i]

            timestamp = row[
                "datetime"
            ]

            close_price = float(
                row["close"]
            )

            # -----------------------------------------------
            # UPDATE EQUITY
            # -----------------------------------------------

            floating_profit = 0.0

            for position in positions:

                floating_profit += (
                    self._calculate_profit(
                        symbol_clean,
                        position[
                            "direction"
                        ],
                        position[
                            "entry"
                        ],
                        close_price,
                        position[
                            "lot"
                        ]
                    )
                )

            equity = (
                balance
                + floating_profit
            )

            if equity > max_equity:
                max_equity = equity

            if max_equity > 0:

                dd = (
                    (
                        max_equity
                        - equity
                    )
                    / max_equity
                    * 100
                )

                max_drawdown = max(
                    max_drawdown,
                    dd
                )

            equity_curve.append(
                {
                    "time": str(
                        timestamp
                    ),
                    "equity": round(
                        equity,
                        2
                    ),
                }
            )

            # -----------------------------------------------
            # CLOSE EXISTING POSITIONS
            # -----------------------------------------------

            closed_positions = []

            for position in list(
                positions
            ):

                should_close, exit_price, reason = (
                    self._check_position_exit(
                        position,
                        row,
                        symbol_clean,
                        risk_params
                    )
                )

                # -------------------------------------------
                # OPPOSITE SIGNAL
                # -------------------------------------------

                if not should_close:

                    opposite = (
                        (
                            position[
                                "direction"
                            ] == "BUY"
                            and
                            signals[i] == -1
                        )
                        or
                        (
                            position[
                                "direction"
                            ] == "SELL"
                            and
                            signals[i] == 1
                        )
                    )

                    if (
                        opposite
                        and
                        risk_params.get(
                            "opposite_signal",
                            False
                        )
                    ):

                        exit_price = (
                            self._exit_price(
                                row,
                                position[
                                    "direction"
                                ],
                                close_price
                            )
                        )

                        should_close = True

                        reason = (
                            "Opposite Signal"
                        )

                if should_close:

                    balance, trade = (
                        self._close_position(
                            position,
                            exit_price,
                            timestamp,
                            symbol_clean,
                            reason,
                            balance,
                            params,
                        )
                    )

                    trades.append(
                        trade
                    )

                    closed_positions.append(
                        position
                    )

                    # ---------------------------------------
                    # MARTINGALE
                    # ---------------------------------------

                    if (
                        trade["profit"] < 0
                        and
                        lot_management.get(
                            "martingale",
                            False
                        )
                    ):

                        multiplier = float(
                            lot_management.get(
                                "multiplier",
                                1.0
                            )
                        )

                        current_lot *= (
                            multiplier
                        )

                        max_lot = float(
                            lot_management.get(
                                "max_lot",
                                100.0
                            )
                        )

                        current_lot = min(
                            current_lot,
                            max_lot
                        )

                    else:

                        current_lot = (
                            base_lot
                        )

            for position in closed_positions:

                if position in positions:
                    positions.remove(
                        position
                    )

            # -----------------------------------------------
            # DAILY LOSS LIMIT
            # -----------------------------------------------

            max_daily_loss = (
                risk_management.get(
                    "max_daily_loss",
                    None
                )
            )

            # Implementasi sederhana:
            # gunakan daily starting balance.
            # Bisa diperluas pada analytics.
            if (
                max_daily_loss is not None
                and
                equity
                <= initial_balance
                * (
                    1
                    - float(
                        max_daily_loss
                    ) / 100
                )
            ):
                continue

            # -----------------------------------------------
            # MAX DRAWDOWN LIMIT
            # -----------------------------------------------

            max_dd_limit = (
                risk_management.get(
                    "max_drawdown",
                    None
                )
            )

            if (
                max_dd_limit is not None
                and
                max_drawdown
                >= float(
                    max_dd_limit
                )
            ):
                continue

            # -----------------------------------------------
            # OPEN NEW POSITION
            # -----------------------------------------------

            signal = int(
                signals[i]
            )

            if signal == 0:
                continue

            if not self._time_allowed(
                timestamp,
                trading_logic
            ):
                continue

            if not self._spread_allowed(
                row,
                trading_logic,
                symbol_clean
            ):
                continue

            if len(positions) >= max_positions:
                continue

            direction = (
                "BUY"
                if signal == 1
                else "SELL"
            )

            entry_price = (
                self._entry_price(
                    row,
                    direction,
                    close_price
                )
            )

            # -----------------------------------------------
            # SLIPPAGE
            # -----------------------------------------------

            slippage_points = float(
                params.get(
                    "slippage_points",
                    trading_logic
                    .get(
                        "execution",
                        {}
                    )
                    .get(
                        "slippage_points",
                        0
                    )
                )
            )

            point = float(
                params.get(
                    "point_size",
                    self._get_point_size(
                        symbol_clean
                    )
                )
            )

            slippage = (
                slippage_points
                * point
            )

            if direction == "BUY":
                entry_price += (
                    slippage
                )
            else:
                entry_price -= (
                    slippage
                )

            # -----------------------------------------------
            # CREATE POSITION
            # -----------------------------------------------

            position = self._create_position(
                symbol_clean,
                direction,
                entry_price,
                timestamp,
                current_lot,
                risk_params
            )

            positions.append(
                position
            )

            # -----------------------------------------------
            # PROGRESS
            # -----------------------------------------------

            if (
                progress_callback
                and
                (
                    i
                    %
                    max(
                        1,
                        total_rows // 50
                    )
                    == 0
                )
            ):

                percent = (
                    45
                    +
                    int(
                        (
                            i
                            / total_rows
                        )
                        * 45
                    )
                )

                self._progress(
                    progress_callback,
                    percent
                )

        # ====================================================
        # CLOSE REMAINING POSITIONS
        # ====================================================

        if positions:

            last_row = df.iloc[-1]

            final_timestamp = (
                last_row["datetime"]
            )

            final_price = float(
                last_row["close"]
            )

            for position in list(
                positions
            ):

                exit_price = (
                    self._exit_price(
                        last_row,
                        position[
                            "direction"
                        ],
                        final_price
                    )
                )

                balance, trade = (
                    self._close_position(
                        position,
                        exit_price,
                        final_timestamp,
                        symbol_clean,
                        "End of Backtest",
                        balance,
                        params,
                    )
                )

                trades.append(
                    trade
                )

            positions = []

        self._progress(
            progress_callback,
            95
        )

        # ====================================================
        # ANALYTICS
        # ====================================================

        print(
            "[5/5] Calculating quantitative analytics..."
        )

        try:

            metrics = (
                QuantitativeAnalytics
                .calculate_metrics(
                    initial_balance,
                    trades,
                    equity_curve
                )
            )

        except Exception as exc:

            print(
                "[ANALYTICS] Error:"
                f" {exc}"
            )

            metrics = {}

        # ====================================================
        # ENGINE METADATA
        # ====================================================

        metrics[
            "engine_version"
        ] = self.VERSION

        metrics[
            "initial_balance"
        ] = initial_balance

        metrics[
            "final_balance"
        ] = round(
            balance,
            2
        )

        metrics[
            "equity"
        ] = round(
            balance,
            2
        )

        metrics[
            "total_rows_processed"
        ] = total_rows

        metrics[
            "symbol_raw"
        ] = raw_symbol

        metrics[
            "symbol_clean"
        ] = symbol_clean

        metrics[
            "start_date"
        ] = str(
            start_date
        )

        metrics[
            "end_date"
        ] = str(
            end_date
        )

        metrics[
            "data_files"
        ] = [
            os.path.basename(f)
            for f in files
        ]

        metrics[
            "data_file_count"
        ] = len(files)

        metrics[
            "max_drawdown_engine"
        ] = round(
            max_drawdown,
            4
        )

        metrics[
            "trades"
        ] = trades

        metrics[
            "equity_curve"
        ] = equity_curve

        metrics[
            "params"
        ] = params

        # ====================================================
        # AI LOGIC RESULT
        # ====================================================

        metrics[
            "ai_logic"
        ] = trading_logic

        metrics[
            "strategy_type"
        ] = trading_logic.get(
            "strategy_type"
        )

        metrics[
            "indicators"
        ] = trading_logic.get(
            "indicators"
        )

        # ====================================================
        # EXECUTION INFO
        # ====================================================

        finished_at = (
            datetime.utcnow()
        )

        metrics[
            "backtest_started_at"
        ] = started_at.isoformat()

        metrics[
            "backtest_finished_at"
        ] = finished_at.isoformat()

        metrics[
            "backtest_duration_seconds"
        ] = round(
            (
                finished_at
                - started_at
            ).total_seconds(),
            3
        )

        # ====================================================
        # SHEET SYNC
        # ====================================================

        if params.get(
            "sync_sheet",
            True
        ):

            try:

                if hasattr(
                    self.sheet_sync,
                    "push_result_async"
                ):

                    self.sheet_sync.push_result_async(
                        metrics
                    )

            except Exception as exc:

                print(
                    "[SHEET] Sync error:"
                    f" {exc}"
                )

        # ====================================================
        # FINAL
        # ====================================================

        self._progress(
            progress_callback,
            100
        )

        print(
            "\n"
            "=================================================="
        )

        print(
            "BACKTEST COMPLETED"
        )

        print(
            f"Trades : {len(trades):,}"
        )

        print(
            f"Balance: {balance:,.2f}"
        )

        print(
            f"Max DD : {max_drawdown:.2f}%"
        )

        print(
            "==================================================\n"
        )

        return metrics

    # ========================================================
    # BATCH BACKTEST
    # ========================================================

    def run_batch(
        self,
        ea_configs,
        progress_callback=None
    ):
        """
        Backtest banyak EA.

        Setiap EA memiliki source MQL5
        dan parameter masing-masing.

        Contoh:

        [
            {
                "ea_name": "EA 01",
                "symbol": "XAUUSD",
                "year": 2024,
                "mql5_code": "..."
            },
            ...
        ]
        """

        results = []

        total = len(
            ea_configs
        )

        if total == 0:
            return results

        for index, config in enumerate(
            ea_configs
        ):

            try:

                base_progress = (
                    index
                    / total
                    * 100
                )

                self._progress(
                    progress_callback,
                    base_progress
                )

                def local_progress(
                    value,
                    base=base_progress
                ):

                    global_progress = (
                        base
                        +
                        (
                            value
                            / 100
                            * (
                                100
                                / total
                            )
                        )
                    )

                    self._progress(
                        progress_callback,
                        global_progress
                    )

                result = self.run(
                    config,
                    progress_callback=local_progress
                )

                results.append(
                    {
                        "success": True,
                        "ea_name": config.get(
                            "ea_name",
                            "EA_MQL5"
                        ),
                        "result": result,
                    }
                )

            except Exception as exc:

                print(
                    "\n[BATCH] ERROR:"
                    f" {exc}"
                )

                traceback.print_exc()

                results.append(
                    {
                        "success": False,
                        "ea_name": config.get(
                            "ea_name",
                            "EA_MQL5"
                        ),
                        "error": str(
                            exc
                        ),
                    }
                )

        self._progress(
            progress_callback,
            100
        )

        return results


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Pintarin Laboratorium EA"
    )

    print(
        "Backtest Engine"
    )

    print(
        f"Version: "
        f"{BacktestEngine.VERSION}"
    )

    print(
        "\nData directory:"
    )

    engine = BacktestEngine(
        tick_data_dir="./data"
    )

    print(
        os.path.abspath(
            "./data"
        )
    )

    print(
        "\nTesting XAUUSD 2024..."
    )

    files = engine.find_data_files(
        "XAUUSD",
        "2024-01-01",
        "2024-12-31"
    )

    print(
        f"Found {len(files)} files:"
    )

    for f in files:
        print(
            " - "
            + f
        )