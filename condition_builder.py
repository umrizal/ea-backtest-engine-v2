
import pandas as pd
import numpy as np

def _ensure_series(val):
    if isinstance(val, np.ndarray):
        return pd.Series(val)
    elif not isinstance(val, (pd.Series, pd.DataFrame)):
        return pd.Series(val)
    return val

# ============================================================
# condition_builder.py
# Pintarin Laboratorium EA – Stage 3
#
# Visual / structured entry-rule builder.
# Mengubah daftar kondisi sederhana menjadi sinyal numpy.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from indicator_engine import IndicatorEngine


# Operator yang didukung
OPS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "cross_above": None,  # special
    "cross_below": None,
    "eq": lambda a, b: np.isclose(a, b, atol=1e-9),
}


class ConditionBuilder:
    """
    Format kondisi (JSON dari UI):

    {
      "buy": [
        {"left": "ma_fast", "op": "cross_above", "right": "ma_slow"},
        {"left": "rsi", "op": "gt", "right": 50}
      ],
      "sell": [
        {"left": "ma_fast", "op": "cross_below", "right": "ma_slow"},
        {"left": "rsi", "op": "lt", "right": 50}
      ],
      "logic": "and"   # or "or" antar kondisi dalam sisi yang sama
    }

    left/right bisa:
      - nama kolom indikator (ma_fast, rsi, close, ...)
      - angka literal
    """

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        self.rules = rules or {
            "buy": [{"left": "ma_fast", "op": "cross_above", "right": "ma_slow"}],
            "sell": [{"left": "ma_fast", "op": "cross_below", "right": "ma_slow"}],
            "logic": "and",
        }

    # ----------------------------------------------------------
    # ENSURE INDICATORS
    # ----------------------------------------------------------

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Hitung indikator dasar jika belum ada di df."""
        if df.empty:
            return df
        prices = df["close"].astype(float)

        if "ma_fast" not in df.columns:
            df["ma_fast"] = IndicatorEngine.sma(prices, 10)
        if "ma_slow" not in df.columns:
            df["ma_slow"] = IndicatorEngine.sma(prices, 30)
        if "rsi" not in df.columns:
            df["rsi"] = IndicatorEngine.rsi(prices, 14)
        if "macd" not in df.columns or "macd_signal" not in df.columns:
            macd, sig, hist = IndicatorEngine.macd(prices)
            df["macd"] = macd
            df["macd_signal"] = sig
            df["macd_hist"] = hist
        if "bb_upper" not in df.columns:
            u, m, l = IndicatorEngine.bollinger_bands(prices)
            df["bb_upper"] = u
            df["bb_middle"] = m
            df["bb_lower"] = l
        if "atr" not in df.columns and {"high", "low"}.issubset(df.columns):
            df["atr"] = IndicatorEngine.atr(df)
        if "stoch_k" not in df.columns and {"high", "low"}.issubset(df.columns):
            k, d = IndicatorEngine.stochastic(df)
            df["stoch_k"] = k
            df["stoch_d"] = d

        return df

    # ----------------------------------------------------------
    # EVALUATE SINGLE CONDITION
    # ----------------------------------------------------------

    def _series(self, df: pd.DataFrame, ref) -> np.ndarray:
        if isinstance(ref, (int, float)):
            return np.full(len(df), float(ref))
        col = str(ref)
        if col not in df.columns:
            # coba lowercase
            for c in df.columns:
                if c.lower() == col.lower():
                    return df[c].astype(float).to_numpy()
            return np.zeros(len(df))
        return df[col].astype(float).to_numpy()

    def _eval_cond(self, df: pd.DataFrame, cond: Dict) -> np.ndarray:
        left = self._series(df, cond.get("left", "close"))
        right = self._series(df, cond.get("right", 0))
        op = str(cond.get("op", "gt")).lower()

        n = len(df)
        if op == "cross_above":
            # left crosses above right
            return (left > right) & (np.roll(left, 1) <= np.roll(right, 1))
        if op == "cross_below":
            return (left < right) & (np.roll(left, 1) >= np.roll(right, 1))

        fn = OPS.get(op)
        if fn is None:
            return np.zeros(n, dtype=bool)
        return fn(left, right)

    # ----------------------------------------------------------
    # GENERATE SIGNALS
    # ----------------------------------------------------------

    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """
        Returns int array: 1=BUY, -1=SELL, 0=HOLD
        """
        df = self.ensure_columns(df.copy())
        n = len(df)
        if n == 0:
            return np.zeros(0, dtype=int)

        logic = str(self.rules.get("logic", "and")).lower()
        buy_conds = self.rules.get("buy") or []
        sell_conds = self.rules.get("sell") or []

        def combine(conds):
            if not conds:
                return np.zeros(n, dtype=bool)
            masks = [self._eval_cond(df, c) for c in conds]
            if logic == "or":
                out = masks[0].copy()
                for m in masks[1:]:
                    out |= m
                return out
            out = masks[0].copy()
            for m in masks[1:]:
                out &= m
            return out

        buy = combine(buy_conds)
        sell = combine(sell_conds)

        signals = np.zeros(n, dtype=int)
        signals[buy] = 1
        signals[sell] = -1
        # jika bentrok di bar yang sama, prioritaskan 0
        conflict = buy & sell
        signals[conflict] = 0
        if n > 0:
            signals[0] = 0  # bar pertama invalid untuk cross

        return signals

    # ----------------------------------------------------------
    # PRESETS (untuk UI dropdown)
    # ----------------------------------------------------------

    @staticmethod
    def presets() -> Dict[str, Dict]:
        return {
            "ma_crossover": {
                "buy": [{"left": "ma_fast", "op": "cross_above", "right": "ma_slow"}],
                "sell": [{"left": "ma_fast", "op": "cross_below", "right": "ma_slow"}],
                "logic": "and",
            },
            "ma_rsi_filter": {
                "buy": [
                    {"left": "ma_fast", "op": "cross_above", "right": "ma_slow"},
                    {"left": "rsi", "op": "gt", "right": 50},
                ],
                "sell": [
                    {"left": "ma_fast", "op": "cross_below", "right": "ma_slow"},
                    {"left": "rsi", "op": "lt", "right": 50},
                ],
                "logic": "and",
            },
            "rsi_oversold": {
                "buy": [{"left": "rsi", "op": "cross_above", "right": 30}],
                "sell": [{"left": "rsi", "op": "cross_below", "right": 70}],
                "logic": "and",
            },
            "macd_cross": {
                "buy": [{"left": "macd", "op": "cross_above", "right": "macd_signal"}],
                "sell": [{"left": "macd", "op": "cross_below", "right": "macd_signal"}],
                "logic": "and",
            },
            "bollinger_reversion": {
                "buy": [{"left": "close", "op": "cross_below", "right": "bb_lower"}],
                "sell": [{"left": "close", "op": "cross_above", "right": "bb_upper"}],
                "logic": "and",
            },
            "breakout_20": {
                "buy": [{"left": "close", "op": "gt", "right": "ma_slow"}],  # proxy
                "sell": [{"left": "close", "op": "lt", "right": "ma_fast"}],
                "logic": "and",
            },
        }

    @staticmethod
    def available_fields() -> List[str]:
        return [
            "close", "open", "high", "low",
            "ma_fast", "ma_slow",
            "rsi", "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower",
            "atr", "stoch_k", "stoch_d",
        ]

    @staticmethod
    def available_ops() -> List[Dict[str, str]]:
        return [
            {"value": "cross_above", "label": "Cross Above"},
            {"value": "cross_below", "label": "Cross Below"},
            {"value": "gt", "label": ">"},
            {"value": "gte", "label": ">="},
            {"value": "lt", "label": "<"},
            {"value": "lte", "label": "<="},
            {"value": "eq", "label": "="},
        ]

    def to_dict(self) -> Dict:
        return self.rules
