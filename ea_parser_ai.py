# ============================================================
# ea_parser_ai.py
# Pintarin Laboratorium EA - Stage 1
#
# Modul kalibrasi & sinkronisasi:
#   Hasil AI structured  →  Parameter Python yang siap dipakai
#   Indicator Engine + Signal Generator
#
# Digunakan oleh:
#   - BacktestEngine
#   - LiveSimulator
#   - Transpiler
# ============================================================

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from indicator_engine import IndicatorEngine


# ============================================================
# DEFAULTS (sinkron dengan ai_explainer & backtest_engine)
# ============================================================

DEFAULT_LOGIC: Dict[str, Any] = {
    "strategy_type": "ma_crossover",
    "indicators": [
        {"name": "MA", "type": "SMA", "period": 10, "role": "fast"},
        {"name": "MA", "type": "SMA", "period": 30, "role": "slow"},
    ],
    "entry_rules": {
        "buy": ["fast MA crosses above slow MA"],
        "sell": ["fast MA crosses below slow MA"],
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
}


class EAParserAI:
    """
    Mengubah hasil analyze_structured() menjadi:
      - parameter yang sudah dikalibrasi
      - indikator yang dihitung
      - sinyal buy/sell yang siap di-simulator
    """

    def __init__(self, trading_logic: Optional[Dict[str, Any]] = None):
        self.logic = self._normalize(trading_logic or DEFAULT_LOGIC.copy())

    # --------------------------------------------------------
    # NORMALIZE
    # --------------------------------------------------------

    def _normalize(self, logic: Dict[str, Any]) -> Dict[str, Any]:
        result = DEFAULT_LOGIC.copy()

        for key in result:
            if key in logic and logic[key] is not None:
                if isinstance(result[key], dict) and isinstance(logic[key], dict):
                    result[key] = {**result[key], **logic[key]}
                else:
                    result[key] = logic[key]

        # pastikan indicators list of dict
        inds = result.get("indicators", [])
        cleaned = []
        for ind in inds:
            if isinstance(ind, str):
                cleaned.append({"name": ind, "period": 14})
            elif isinstance(ind, dict):
                cleaned.append(ind)
        result["indicators"] = cleaned or DEFAULT_LOGIC["indicators"]

        # strategy_type lower
        result["strategy_type"] = str(result.get("strategy_type", "ma_crossover")).lower()

        return result

    # --------------------------------------------------------
    # PARAMETER GETTERS (kalibrasi)
    # --------------------------------------------------------

    def get_risk_params(self) -> Dict[str, float]:
        er = self.logic.get("exit_rules", {})
        return {
            "TakeProfit": float(er.get("tp", 50.0)),
            "StopLoss": float(er.get("sl", 30.0)),
            "TrailingStop": float(er.get("trailing", 0.0)),
            "TrailingStep": 5.0,
            "BreakEven": float(er.get("breakeven", 0.0)),
            "tp_unit": er.get("tp_unit", "pips"),
            "sl_unit": er.get("sl_unit", "pips"),
            "opposite_signal": bool(er.get("opposite_signal", False)),
        }

    def get_lot_params(self) -> Dict[str, Any]:
        lm = self.logic.get("lot_management", {})
        return {
            "type": lm.get("type", "fixed"),
            "base_lot": float(lm.get("base_lot", 0.1)),
            "multiplier": float(lm.get("multiplier", 1.0)),
            "martingale": bool(lm.get("martingale", False)),
            "max_lot": float(lm.get("max_lot", 100.0)),
        }

    def get_risk_management(self) -> Dict[str, Any]:
        return self.logic.get("risk_management", DEFAULT_LOGIC["risk_management"]).copy()

    def get_strategy_type(self) -> str:
        return self.logic.get("strategy_type", "ma_crossover")

    def get_indicators_config(self) -> List[Dict]:
        return self.logic.get("indicators", [])

    # --------------------------------------------------------
    # INDICATOR CALCULATION
    # --------------------------------------------------------

    def calculate_indicators(self, df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
        """
        Menghitung semua indikator berdasarkan config dari AI
        dan menambahkan kolom ke DataFrame.
        """
        if df.empty:
            return df

        prices = df[price_col].astype(float)
        strategy = self.get_strategy_type()
        inds = self.get_indicators_config()

        # --- MA family ---
        fast_period = 10
        slow_period = 30
        ma_type = "SMA"

        for ind in inds:
            name = str(ind.get("name", "")).upper()
            role = str(ind.get("role", "")).lower()
            period = int(ind.get("period", 14))
            itype = str(ind.get("type", "SMA")).upper()

            if "MA" in name or itype in ("SMA", "EMA"):
                if role == "fast" or (not role and period < slow_period):
                    fast_period = period
                    ma_type = itype
                elif role == "slow" or period > fast_period:
                    slow_period = period

        if ma_type == "EMA":
            df["ma_fast"] = IndicatorEngine.ema(prices, fast_period)
            df["ma_slow"] = IndicatorEngine.ema(prices, slow_period)
        else:
            df["ma_fast"] = IndicatorEngine.sma(prices, fast_period)
            df["ma_slow"] = IndicatorEngine.sma(prices, slow_period)

        # --- RSI ---
        rsi_period = 14
        for ind in inds:
            if "RSI" in str(ind.get("name", "")).upper():
                rsi_period = int(ind.get("period", 14))
                break
        df["rsi"] = IndicatorEngine.rsi(prices, rsi_period)

        # --- MACD ---
        if strategy in ("macd", "trend_following") or any(
            "MACD" in str(i.get("name", "")).upper() for i in inds
        ):
            macd, signal, hist = IndicatorEngine.macd(prices)
            df["macd"] = macd
            df["macd_signal"] = signal
            df["macd_hist"] = hist

        # --- Bollinger ---
        if strategy == "bollinger" or any(
            "BOLL" in str(i.get("name", "")).upper() or "BAND" in str(i.get("name", "")).upper()
            for i in inds
        ):
            upper, mid, lower = IndicatorEngine.bollinger_bands(prices)
            df["bb_upper"] = upper
            df["bb_middle"] = mid
            df["bb_lower"] = lower

        # --- Stochastic ---
        if strategy == "stochastic" or any(
            "STOCH" in str(i.get("name", "")).upper() for i in inds
        ):
            k, d = IndicatorEngine.stochastic(df)
            df["stoch_k"] = k
            df["stoch_d"] = d

        # --- ATR (untuk trailing / volatility filter) ---
        if "high" in df.columns and "low" in df.columns:
            df["atr"] = IndicatorEngine.atr(df)

        return df

    # --------------------------------------------------------
    # SIGNAL GENERATION (sinkron dengan engine)
    # --------------------------------------------------------

    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        """
        Menghasilkan array sinyal:
          1  = BUY
         -1  = SELL
          0  = HOLD
        """
        n = len(df)
        if n == 0:
            return np.zeros(0, dtype=int)

        signals = np.zeros(n, dtype=int)
        strategy = self.get_strategy_type()

        # Pastikan indikator sudah ada
        if "ma_fast" not in df.columns or "ma_slow" not in df.columns:
            df = self.calculate_indicators(df)

        ma_fast = df["ma_fast"].to_numpy()
        ma_slow = df["ma_slow"].to_numpy()
        rsi = df.get("rsi", pd.Series(np.full(n, 50.0))).to_numpy()

        if strategy in ("ma_crossover", "trend_following", "scalping"):
            # Classic crossover
            buy = (ma_fast > ma_slow) & (np.roll(ma_fast, 1) <= np.roll(ma_slow, 1))
            sell = (ma_fast < ma_slow) & (np.roll(ma_fast, 1) >= np.roll(ma_slow, 1))
            # Filter RSI jika ada
            if "rsi" in df.columns:
                buy = buy & (rsi > 45)
                sell = sell & (rsi < 55)
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        elif strategy == "rsi":
            buy = (rsi < 30) & (np.roll(rsi, 1) >= 30)
            sell = (rsi > 70) & (np.roll(rsi, 1) <= 70)
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        elif strategy == "macd" and "macd" in df.columns and "macd_signal" in df.columns:
            macd = df["macd"].to_numpy()
            sig = df["macd_signal"].to_numpy()
            buy = (macd > sig) & (np.roll(macd, 1) <= np.roll(sig, 1))
            sell = (macd < sig) & (np.roll(macd, 1) >= np.roll(sig, 1))
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        elif strategy == "bollinger" and "bb_upper" in df.columns:
            close = df["close"].astype(float).to_numpy()
            upper = df["bb_upper"].to_numpy()
            lower = df["bb_lower"].to_numpy()
            # Mean reversion
            buy = (close < lower) & (np.roll(close, 1) >= np.roll(lower, 1))
            sell = (close > upper) & (np.roll(close, 1) <= np.roll(upper, 1))
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        elif strategy == "stochastic" and "stoch_k" in df.columns:
            k = df["stoch_k"].to_numpy()
            d = df.get("stoch_d", k).to_numpy()
            buy = (k < 20) & (k > d) & (np.roll(k, 1) <= np.roll(d, 1))
            sell = (k > 80) & (k < d) & (np.roll(k, 1) >= np.roll(d, 1))
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        elif strategy == "breakout":
            close = df["close"].astype(float)
            high_20 = close.rolling(20, min_periods=1).max().to_numpy()
            low_20 = close.rolling(20, min_periods=1).min().to_numpy()
            buy = close.to_numpy() > np.roll(high_20, 1)
            sell = close.to_numpy() < np.roll(low_20, 1)
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        else:
            # Fallback: MA crossover
            buy = (ma_fast > ma_slow) & (np.roll(ma_fast, 1) <= np.roll(ma_slow, 1))
            sell = (ma_fast < ma_slow) & (np.roll(ma_fast, 1) >= np.roll(ma_slow, 1))
            signals = np.where(buy, 1, np.where(sell, -1, 0))

        # Bersihkan sinyal di bar pertama (tidak valid karena roll)
        if n > 0:
            signals[0] = 0

        return signals

    # --------------------------------------------------------
    # FULL PIPELINE HELPER
    # --------------------------------------------------------

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, Dict]:
        """
        Satu pintu masuk:
          DataFrame + trading_logic → (df_dengan_indikator, signals, params)
        """
        df = self.calculate_indicators(df.copy())
        signals = self.generate_signals(df)
        params = {
            "risk": self.get_risk_params(),
            "lot": self.get_lot_params(),
            "risk_management": self.get_risk_management(),
            "strategy_type": self.get_strategy_type(),
            "indicators": self.get_indicators_config(),
        }
        return df, signals, params


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def parse_and_calibrate(trading_logic: Dict[str, Any], df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, Dict]:
    """Shortcut: logic dari AI → siap di-simulator."""
    parser = EAParserAI(trading_logic)
    return parser.prepare(df)
