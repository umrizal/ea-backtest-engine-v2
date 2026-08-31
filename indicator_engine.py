
import pandas as pd
import numpy as np

def _ensure_series(val):
    if isinstance(val, np.ndarray):
        return pd.Series(val)
    elif not isinstance(val, (pd.Series, pd.DataFrame)):
        return pd.Series(val)
    return val

import numpy as np
import pandas as pd

class IndicatorEngine:
    @staticmethod
    def sma(series, period):
        return _ensure_series(series).rolling(window=period, min_periods=1).mean().to_numpy()

    @staticmethod
    def ema(series, period):
        return series.ewm(span=period, adjust=False).mean().to_numpy()

    @staticmethod
    def rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
        rs = gain / loss
        return (100 - (100 / (1 + rs))).fillna(50).to_numpy()

    @staticmethod
    def macd(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.to_numpy(), signal_line.to_numpy(), histogram.to_numpy()

    @staticmethod
    def bollinger_bands(series, period=20, std_dev=2.0):
        sma = _ensure_series(series).rolling(window=period, min_periods=1).mean()
        std = _ensure_series(series).rolling(window=period, min_periods=1).std().fillna(0)
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper.to_numpy(), sma.to_numpy(), lower.to_numpy()

    @staticmethod
    def atr(df, high_col='high', low_col='low', close_col='close', period=14):
        if high_col not in df.columns or low_col not in df.columns:
            return np.zeros(len(df))
        high = df[high_col].astype(float)
        low = df[low_col].astype(float)
        close = df[close_col].astype(float).shift(1)
        tr = np.maximum(high - low, np.maximum(np.abs(high - close), np.abs(low - close)))
        return pd.Series(tr).rolling(window=period, min_periods=1).mean().to_numpy()

    @staticmethod
    def stochastic(df, high_col='high', low_col='low', close_col='close', k_period=14, d_period=3):
        if high_col not in df.columns:
            return np.full(len(df), 50.0), np.full(len(df), 50.0)
        low_min = df[low_col].astype(float).rolling(k_period).min()
        high_max = df[high_col].astype(float).rolling(k_period).max()
        k = 100 * ((df[close_col].astype(float) - low_min) / (high_max - low_min))
        d = _ensure_series(k).rolling(d_period).mean()
        return k.fillna(50).to_numpy(), d.fillna(50).to_numpy()
