import numpy as np
import pandas as pd
from mql_parser import MQL5Parser
from indicator_engine import IndicatorEngine

class MQL5Transpiler:
    def __init__(self, mql_code):
        self.parser = MQL5Parser(mql_code)
        self.ast = self.parser.ast
        self.params = self.ast["inputs"]

    def get_risk_params(self, default_params):
        return {
            "TakeProfit": float(self.params.get("TakeProfit", self.params.get("InpTakeProfit", default_params.get("tp_pips", 50.0)))),
            "StopLoss": float(self.params.get("StopLoss", self.params.get("InpStopLoss", default_params.get("sl_pips", 30.0)))),
            "TrailingStop": float(self.params.get("TrailingStop", self.params.get("InpTrailingStop", 0.0))),
            "TrailingStep": float(self.params.get("TrailingStep", 5.0)),
            "BreakEven": float(self.params.get("BreakEven", 0.0)),
            "LotMultiplier": float(self.params.get("LotMultiplier", self.params.get("MartingaleFactor", 1.0)))
        }

    def compile_signals(self, df, price_col='close'):
        prices = df[price_col].astype(float)
        total_rows = len(prices)
        
        buy_signals = np.zeros(total_rows, dtype=bool)
        sell_signals = np.zeros(total_rows, dtype=bool)

        fast_p = int(self.params.get("FastMA", self.params.get("InpFastMA", 10)))
        slow_p = int(self.params.get("SlowMA", self.params.get("InpSlowMA", 30)))
        rsi_p = int(self.params.get("RSIPeriod", self.params.get("InpRSI", 14)))

        ma_fast = IndicatorEngine.sma(prices, fast_p)
        ma_slow = IndicatorEngine.sma(prices, slow_p)
        rsi = IndicatorEngine.rsi(prices, rsi_p)

        code_upper = self.parser.code.upper()
        
        if 'IMA' in code_upper:
            buy_signals = (ma_fast > ma_slow) & (np.roll(ma_fast, 1) <= np.roll(ma_slow, 1))
            sell_signals = (ma_fast < ma_slow) & (np.roll(ma_fast, 1) >= np.roll(ma_slow, 1))
            if 'IRSI' in code_upper:
                buy_signals &= (rsi > 50)
                sell_signals &= (rsi < 50)
        elif 'IRSI' in code_upper:
            buy_signals = (rsi < 30) & (np.roll(rsi, 1) >= 30)
            sell_signals = (rsi > 70) & (np.roll(rsi, 1) <= 70)
        else:
            high_20 = prices.rolling(window=20, min_periods=1).max().to_numpy()
            low_20 = prices.rolling(window=20, min_periods=1).min().to_numpy()
            buy_signals = prices.to_numpy() > np.roll(high_20, 1)
            sell_signals = prices.to_numpy() < np.roll(low_20, 1)

        return buy_signals, sell_signals
