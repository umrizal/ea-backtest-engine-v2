# ============================================================
# portfolio_compare.py
# Pintarin Laboratorium EA – Stage 3
#
# Multi-EA / Multi-Symbol portfolio comparison
# ============================================================

from __future__ import annotations

import copy
import concurrent.futures
from typing import Any, Callable, Dict, List, Optional

from analytics import QuantitativeAnalytics


class PortfolioComparator:
    """
    Menjalankan beberapa EA / symbol secara paralel,
    lalu merangkum leaderboard + combined equity.
    """

    def __init__(self, engine, max_workers: int = 4):
        self.engine = engine
        self.max_workers = max_workers

    def _run_one(self, item: Dict) -> Dict[str, Any]:
        """
        item = {
          "id": "EA1_XAU",
          "label": "Grid Gold",
          "params": { mql5_code, symbol, start_date, end_date, balance, lot, logic_override? }
        }
        """
        params = copy.deepcopy(item.get("params") or {})
        label = item.get("label") or item.get("id") or params.get("symbol", "unknown")
        eid = item.get("id") or label

        try:
            if hasattr(self.engine, "run"):
                res = self.engine.run(params) or {}
            else:
                res = {}

            metrics = res.get("metrics") or res.get("report") or res
            if not isinstance(metrics, dict):
                metrics = {}

            # pastikan ada field penting
            trades = res.get("trades") or metrics.get("trades") or []
            equity = res.get("equity_curve") or metrics.get("equity_curve") or []

            if not metrics.get("scientific_score") and trades:
                metrics = QuantitativeAnalytics.calculate_metrics(
                    float(params.get("balance") or params.get("initial_balance") or 10000),
                    trades,
                    equity if equity else [{"equity": float(params.get("balance", 10000))}],
                )

            return {
                "id": eid,
                "label": label,
                "success": True,
                "symbol": params.get("symbol"),
                "metrics": {
                    "net_profit": metrics.get("net_profit", 0),
                    "profit_factor": metrics.get("profit_factor", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                    "sortino_ratio": metrics.get("sortino_ratio", 0),
                    "scientific_score": metrics.get("scientific_score", 0),
                    "status_label": metrics.get("status_label", "N/A"),
                    "total_trades": metrics.get("total_trades", 0),
                    "expectancy": metrics.get("expectancy", 0),
                    "is_jackpot_dependent": metrics.get("is_jackpot_dependent", False),
                },
                "trades_count": len(trades),
                "equity_curve": equity[-500:] if isinstance(equity, list) else [],
            }
        except Exception as e:
            return {
                "id": eid,
                "label": label,
                "success": False,
                "error": str(e),
                "metrics": {},
            }

    def compare(
        self,
        items: List[Dict],
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        items: list of EA/symbol configs
        """
        if not items:
            return {"success": False, "error": "Tidak ada item portfolio.", "leaderboard": []}

        results = []
        n = len(items)

        def prog(i):
            if progress_callback:
                try:
                    progress_callback(int((i / max(n, 1)) * 100))
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, n)) as ex:
            futures = {ex.submit(self._run_one, it): i for i, it in enumerate(items)}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
                done += 1
                prog(done)

        # Leaderboard by scientific_score lalu net_profit
        ok = [r for r in results if r.get("success")]
        ok.sort(
            key=lambda r: (
                float(r.get("metrics", {}).get("scientific_score") or 0),
                float(r.get("metrics", {}).get("net_profit") or 0),
            ),
            reverse=True,
        )

        total_net = sum(float(r.get("metrics", {}).get("net_profit") or 0) for r in ok)
        avg_score = (
            sum(float(r.get("metrics", {}).get("scientific_score") or 0) for r in ok) / len(ok)
            if ok
            else 0
        )

        return {
            "success": True,
            "leaderboard": ok,
            "failed": [r for r in results if not r.get("success")],
            "summary": {
                "n_eas": len(ok),
                "portfolio_net_profit": round(total_net, 2),
                "avg_scientific_score": round(avg_score, 2),
                "best": ok[0]["label"] if ok else None,
                "best_score": ok[0]["metrics"].get("scientific_score") if ok else None,
            },
        }
