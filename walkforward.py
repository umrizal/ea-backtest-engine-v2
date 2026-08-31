# ============================================================
# walkforward.py
# Pintarin Laboratorium EA – Stage 3
#
# Walk-Forward Optimization + Monte Carlo robustness test
# ============================================================

from __future__ import annotations

import copy
import random
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class WalkForwardOptimizer:
    """
    Walk-Forward Analysis (WFA):
      - Split data into sequential In-Sample (IS) / Out-of-Sample (OOS) windows
      - Optimize on IS, validate on OOS
      - Aggregate OOS equity for unbiased performance estimate

    Monte Carlo:
      - Shuffle trade returns (or bootstrap blocks)
      - Estimate confidence intervals on max DD, net profit, Sortino
    """

    def __init__(self, engine, progress_callback: Optional[Callable] = None):
        """
        engine: instance BacktestEngine yang punya method run(params) / run_backtest
        """
        self.engine = engine
        self.progress_callback = progress_callback

    def _prog(self, val: int):
        if self.progress_callback:
            try:
                self.progress_callback(int(max(0, min(100, val))))
            except Exception:
                pass

    # ----------------------------------------------------------
    # DATE WINDOW HELPERS
    # ----------------------------------------------------------

    @staticmethod
    def _parse_date(d) -> datetime:
        if isinstance(d, datetime):
            return d
        return pd.to_datetime(d).to_pydatetime()

    def _make_windows(
        self,
        start: str,
        end: str,
        is_months: int = 6,
        oos_months: int = 2,
        step_months: int = 2,
    ) -> List[Dict[str, str]]:
        """
        Generate rolling windows.
        Example: IS=6m, OOS=2m, step=2m
        """
        s = self._parse_date(start)
        e = self._parse_date(end)
        windows = []
        cursor = s

        while True:
            is_start = cursor
            is_end = is_start + timedelta(days=is_months * 30)
            oos_start = is_end
            oos_end = oos_start + timedelta(days=oos_months * 30)

            if oos_end > e:
                break

            windows.append({
                "is_start": is_start.strftime("%Y-%m-%d"),
                "is_end": is_end.strftime("%Y-%m-%d"),
                "oos_start": oos_start.strftime("%Y-%m-%d"),
                "oos_end": oos_end.strftime("%Y-%m-%d"),
            })
            cursor = cursor + timedelta(days=step_months * 30)

        return windows

    # ----------------------------------------------------------
    # SIMPLE GRID / RANDOM SEARCH ON IS
    # ----------------------------------------------------------

    def _search_params(
        self,
        base_params: Dict,
        param_space: Dict[str, List],
        max_trials: int = 20,
    ) -> Tuple[Dict, float]:
        """
        Random search over param_space.
        Score = sortino + 0.5 * profit_factor  (robust default)
        """
        keys = list(param_space.keys())
        if not keys:
            return {}, 0.0

        best_score = -1e18
        best = {}

        for _ in range(max_trials):
            trial = {}
            for k in keys:
                choices = param_space[k]
                trial[k] = random.choice(choices)

            p = copy.deepcopy(base_params)
            # Apply into logic_override or top-level
            override = p.get("logic_override") or {}
            exit_r = override.get("exit_rules") or p.get("exit_rules") or {}
            lot_m = override.get("lot_management") or p.get("lot_management") or {}

            if "tp" in trial:
                exit_r["tp"] = trial["tp"]
            if "sl" in trial:
                exit_r["sl"] = trial["sl"]
            if "base_lot" in trial:
                lot_m["base_lot"] = trial["base_lot"]
                p["lot"] = trial["base_lot"]
            if "trailing" in trial:
                exit_r["trailing"] = trial["trailing"]

            override["exit_rules"] = exit_r
            override["lot_management"] = lot_m
            p["logic_override"] = override

            try:
                res = self._run_engine(p)
                metrics = self._extract_metrics(res)
                score = (
                    float(metrics.get("sortino_ratio") or 0)
                    + 0.5 * float(metrics.get("profit_factor") or 0)
                    - 0.3 * float(metrics.get("max_drawdown_pct") or 0) / 10.0
                )
                if score > best_score:
                    best_score = score
                    best = trial
            except Exception:
                continue

        return best, best_score

    def _run_engine(self, params: Dict) -> Dict:
        if hasattr(self.engine, "run"):
            return self.engine.run(params) or {}
        if hasattr(self.engine, "run_backtest"):
            return self.engine.run_backtest(**{
                k: params[k]
                for k in ("mql5_code", "initial_balance", "start_date", "end_date")
                if k in params
            }) or {}
        raise RuntimeError("BacktestEngine tidak punya method run/run_backtest")

    def _extract_metrics(self, res: Dict) -> Dict:
        if not res:
            return {}
        if "metrics" in res and isinstance(res["metrics"], dict):
            return res["metrics"]
        if "report" in res and isinstance(res["report"], dict):
            return res["report"]
        return res

    # ----------------------------------------------------------
    # MAIN WALK-FORWARD
    # ----------------------------------------------------------

    def run(
        self,
        base_params: Dict[str, Any],
        param_space: Optional[Dict[str, List]] = None,
        is_months: int = 6,
        oos_months: int = 2,
        step_months: int = 2,
        max_trials_per_window: int = 15,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            windows: [...],
            oos_metrics_aggregate: {...},
            best_params_per_window: [...],
            efficiency_ratio: float,   # OOS net / IS net (ideal ~0.5-1.0)
          }
        """
        start = base_params.get("start_date", "2024-01-01")
        end = base_params.get("end_date", "2024-12-31")

        if param_space is None:
            param_space = {
                "tp": [30, 40, 50, 60, 80, 100],
                "sl": [20, 25, 30, 40, 50],
                "base_lot": [0.05, 0.1, 0.15, 0.2],
            }

        windows = self._make_windows(start, end, is_months, oos_months, step_months)
        if not windows:
            return {
                "success": False,
                "error": "Tidak cukup data untuk membentuk window walk-forward.",
                "windows": [],
            }

        results = []
        oos_net_total = 0.0
        is_net_total = 0.0
        all_oos_trades = []

        n = len(windows)
        for i, w in enumerate(windows):
            self._prog(5 + int(i / max(n, 1) * 80))

            # --- IS optimize ---
            is_params = copy.deepcopy(base_params)
            is_params["start_date"] = w["is_start"]
            is_params["end_date"] = w["is_end"]

            best_params, best_score = self._search_params(
                is_params, param_space, max_trials=max_trials_per_window
            )

            # Run IS with best
            is_run_params = copy.deepcopy(is_params)
            ov = is_run_params.get("logic_override") or {}
            er = ov.get("exit_rules") or {}
            lm = ov.get("lot_management") or {}
            if "tp" in best_params:
                er["tp"] = best_params["tp"]
            if "sl" in best_params:
                er["sl"] = best_params["sl"]
            if "base_lot" in best_params:
                lm["base_lot"] = best_params["base_lot"]
                is_run_params["lot"] = best_params["base_lot"]
            ov["exit_rules"] = er
            ov["lot_management"] = lm
            is_run_params["logic_override"] = ov

            try:
                is_res = self._run_engine(is_run_params)
                is_m = self._extract_metrics(is_res)
            except Exception as e:
                is_m = {"error": str(e), "net_profit": 0}

            # --- OOS validate ---
            oos_params = copy.deepcopy(is_run_params)
            oos_params["start_date"] = w["oos_start"]
            oos_params["end_date"] = w["oos_end"]

            try:
                oos_res = self._run_engine(oos_params)
                oos_m = self._extract_metrics(oos_res)
                trades = oos_res.get("trades") or oos_m.get("trades") or []
                all_oos_trades.extend(trades)
            except Exception as e:
                oos_m = {"error": str(e), "net_profit": 0}
                trades = []

            is_net = float(is_m.get("net_profit") or 0)
            oos_net = float(oos_m.get("net_profit") or 0)
            is_net_total += is_net
            oos_net_total += oos_net

            results.append({
                "window": w,
                "best_params": best_params,
                "is_score": round(best_score, 3),
                "is_metrics": {
                    "net_profit": round(is_net, 2),
                    "profit_factor": is_m.get("profit_factor"),
                    "max_drawdown_pct": is_m.get("max_drawdown_pct"),
                    "sortino_ratio": is_m.get("sortino_ratio"),
                    "total_trades": is_m.get("total_trades"),
                },
                "oos_metrics": {
                    "net_profit": round(oos_net, 2),
                    "profit_factor": oos_m.get("profit_factor"),
                    "max_drawdown_pct": oos_m.get("max_drawdown_pct"),
                    "sortino_ratio": oos_m.get("sortino_ratio"),
                    "total_trades": oos_m.get("total_trades"),
                },
            })

        efficiency = (oos_net_total / is_net_total) if abs(is_net_total) > 1e-9 else 0.0

        # Aggregate OOS
        agg = {
            "oos_net_profit": round(oos_net_total, 2),
            "is_net_profit": round(is_net_total, 2),
            "efficiency_ratio": round(efficiency, 3),
            "n_windows": n,
            "verdict": (
                "ROBUST" if 0.4 <= efficiency <= 1.5 and oos_net_total > 0
                else ("OVERFIT" if efficiency < 0.3 else "UNSTABLE")
            ),
        }

        self._prog(90)

        return {
            "success": True,
            "windows": results,
            "aggregate": agg,
            "oos_trades_count": len(all_oos_trades),
        }


class MonteCarloSimulator:
    """
    Monte Carlo robustness on a list of closed trade profits.
    Methods:
      - shuffle: random permutation of trade order
      - bootstrap: sample with replacement
    """

    def __init__(self, n_simulations: int = 1000, seed: Optional[int] = 42):
        self.n = n_simulations
        self.rng = np.random.default_rng(seed)

    def run(
        self,
        trade_profits: List[float],
        initial_balance: float = 10000.0,
        method: str = "shuffle",
    ) -> Dict[str, Any]:
        profits = np.array([float(p) for p in trade_profits if p is not None], dtype=float)
        if len(profits) < 5:
            return {
                "success": False,
                "error": "Minimal 5 closed trades untuk Monte Carlo.",
            }

        final_balances = []
        max_dds = []
        net_profits = []

        for _ in range(self.n):
            if method == "bootstrap":
                sample = self.rng.choice(profits, size=len(profits), replace=True)
            else:
                sample = profits.copy()
                self.rng.shuffle(sample)

            equity = initial_balance
            peak = equity
            max_dd = 0.0
            for p in sample:
                equity += p
                peak = max(peak, equity)
                if peak > 0:
                    dd = (peak - equity) / peak * 100
                    max_dd = max(max_dd, dd)

            final_balances.append(equity)
            max_dds.append(max_dd)
            net_profits.append(equity - initial_balance)

        final_balances = np.array(final_balances)
        max_dds = np.array(max_dds)
        net_profits = np.array(net_profits)

        def pct(arr, q):
            return float(np.percentile(arr, q))

        return {
            "success": True,
            "n_simulations": self.n,
            "method": method,
            "n_trades": len(profits),
            "net_profit": {
                "mean": round(float(net_profits.mean()), 2),
                "median": round(float(np.median(net_profits)), 2),
                "p5": round(pct(net_profits, 5), 2),
                "p25": round(pct(net_profits, 25), 2),
                "p75": round(pct(net_profits, 75), 2),
                "p95": round(pct(net_profits, 95), 2),
            },
            "max_drawdown_pct": {
                "mean": round(float(max_dds.mean()), 2),
                "median": round(float(np.median(max_dds)), 2),
                "p95": round(pct(max_dds, 95), 2),
                "worst": round(float(max_dds.max()), 2),
            },
            "prob_profit": round(float((net_profits > 0).mean() * 100), 1),
            "prob_ruin_20pct": round(
                float((max_dds >= 20).mean() * 100), 1
            ),
            "verdict": self._verdict(net_profits, max_dds),
        }

    @staticmethod
    def _verdict(nets: np.ndarray, dds: np.ndarray) -> str:
        prob_profit = (nets > 0).mean()
        p95_dd = np.percentile(dds, 95)
        if prob_profit >= 0.7 and p95_dd < 25:
            return "ROBUST"
        if prob_profit >= 0.5 and p95_dd < 40:
            return "MODERATE"
        return "FRAGILE"
