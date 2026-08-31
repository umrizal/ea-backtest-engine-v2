
import pandas as pd
import numpy as np

def _ensure_series(val):
    if isinstance(val, np.ndarray):
        return pd.Series(val)
    elif not isinstance(val, (pd.Series, pd.DataFrame)):
        return pd.Series(val)
    return val

# ============================================================
# transpiler.py
# Pintarin Laboratorium EA - Stage 1
#
# MQL5 → Python Strategy Transpiler
# Sekarang memakai EAParserAI (hasil structured AI)
# sebagai sumber logika utama.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from mql_parser import MQL5Parser
from ea_parser_ai import EAParserAI, DEFAULT_LOGIC
from indicator_engine import IndicatorEngine


class MQL5Transpiler:
    """
    Mengubah kode MQL5 (atau hasil AI structured) menjadi
    sinyal trading Python yang siap dijalankan di BacktestEngine
    dan LiveSimulator.
    """

    def __init__(
        self,
        mql_code: str = "",
        trading_logic: Optional[Dict[str, Any]] = None,
    ):
        self.mql_code = mql_code or ""
        self.parser = MQL5Parser(self.mql_code)
        self.ast = self.parser.ast

        # Prioritas: trading_logic dari AI > hasil regex parser
        if trading_logic:
            self.logic = trading_logic
        else:
            # Bangun logic dasar dari AST lama
            self.logic = self._ast_to_logic()

        self.ea_parser = EAParserAI(self.logic)
        self.params = self.ea_parser.get_risk_params()

    # --------------------------------------------------------
    # CONVERT AST LAMA → STRUCTURED LOGIC
    # --------------------------------------------------------

    def _ast_to_logic(self) -> Dict[str, Any]:
        logic = DEFAULT_LOGIC.copy()
        inputs = self.ast.get("inputs", {})

        # Lot & risk dari input
        if "Lot" in inputs or "Lots" in inputs or "LotSize" in inputs:
            logic["lot_management"]["base_lot"] = float(
                inputs.get("Lot") or inputs.get("Lots") or inputs.get("LotSize") or 0.1
            )

        if "TakeProfit" in inputs or "InpTakeProfit" in inputs:
            logic["exit_rules"]["tp"] = float(
                inputs.get("TakeProfit") or inputs.get("InpTakeProfit") or 50
            )
        if "StopLoss" in inputs or "InpStopLoss" in inputs:
            logic["exit_rules"]["sl"] = float(
                inputs.get("StopLoss") or inputs.get("InpStopLoss") or 30
            )
        if "TrailingStop" in inputs or "InpTrailingStop" in inputs:
            logic["exit_rules"]["trailing"] = float(
                inputs.get("TrailingStop") or inputs.get("InpTrailingStop") or 0
            )
        if "LotMultiplier" in inputs or "MartingaleFactor" in inputs:
            mult = float(
                inputs.get("LotMultiplier") or inputs.get("MartingaleFactor") or 1.0
            )
            logic["lot_management"]["multiplier"] = mult
            if mult > 1.0:
                logic["lot_management"]["martingale"] = True
                logic["lot_management"]["type"] = "martingale"

        # Indicators dari AST
        inds = []
        for ind in self.ast.get("indicators", []):
            itype = ind.get("type", "iMA")
            if itype == "iMA":
                inds.append({"name": "MA", "type": "SMA", "period": 14})
            elif itype == "iRSI":
                inds.append({"name": "RSI", "period": 14})
            elif itype == "iMACD":
                inds.append({"name": "MACD"})
            elif itype == "iBands":
                inds.append({"name": "Bollinger"})

        if inds:
            logic["indicators"] = inds
            # Deteksi strategy sederhana
            names = " ".join(i["name"].lower() for i in inds)
            if "rsi" in names and "ma" not in names:
                logic["strategy_type"] = "rsi"
            elif "macd" in names:
                logic["strategy_type"] = "macd"
            elif "bollinger" in names:
                logic["strategy_type"] = "bollinger"
            else:
                logic["strategy_type"] = "ma_crossover"

        return logic

    # --------------------------------------------------------
    # PUBLIC API (kompatibel dengan versi lama)
    # --------------------------------------------------------

    def get_risk_params(self, default_params: Optional[Dict] = None) -> Dict[str, float]:
        """Kompatibel dengan pemanggilan lama."""
        risk = self.ea_parser.get_risk_params()
        if default_params:
            risk["TakeProfit"] = float(
                risk.get("TakeProfit") or default_params.get("tp_pips", 50.0)
            )
            risk["StopLoss"] = float(
                risk.get("StopLoss") or default_params.get("sl_pips", 30.0)
            )
        return risk

    def compile_signals(
        self, df: pd.DataFrame, price_col: str = "close"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Menghasilkan (buy_signals, sell_signals) boolean array.
        Kompatibel dengan versi lama.
        """
        df_ready, signals, _ = self.ea_parser.prepare(df)
        buy = signals == 1
        sell = signals == -1
        return buy, sell

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, Dict]:
        """Full pipeline: df → (df+indicators, signals, params)."""
        return self.ea_parser.prepare(df)

    def get_trading_logic(self) -> Dict[str, Any]:
        return self.ea_parser.logic
