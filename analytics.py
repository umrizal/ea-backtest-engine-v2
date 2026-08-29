import numpy as np

class QuantitativeAnalytics:
    @staticmethod
    def calculate_metrics(initial_balance, trades, equity_curve):
        if not trades:
            return QuantitativeAnalytics._empty_metrics(initial_balance)

        closed_trades = [t for t in trades if t.get("status") == "closed"]
        profits = [t["profit"] for t in closed_trades]
        
        net_profit = sum(profits)
        gross_profit = sum([p for p in profits if p > 0])
        gross_loss = abs(sum([p for p in profits if p < 0]))
        
        win_trades = [p for p in profits if p > 0]
        loss_trades = [p for p in profits if p < 0]
        
        win_count = len(win_trades)
        loss_count = len(loss_trades)
        total_closed = len(closed_trades)
        
        win_rate = (win_count / total_closed * 100) if total_closed else 0.0
        loss_rate = (loss_count / total_closed * 100) if total_closed else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.99 if gross_profit > 0 else 0.0)
        
        avg_win = (sum(win_trades) / win_count) if win_count else 0.0
        avg_loss = (abs(sum(loss_trades)) / loss_count) if loss_count else 0.0
        avg_trade = (net_profit / total_closed) if total_closed else 0.0
        expectancy = ((win_rate / 100) * avg_win) - ((loss_rate / 100) * avg_loss)

        # Sortino Ratio Calculation
        downside_dev = np.sqrt(np.mean([p**2 for p in profits if p < 0])) if loss_count else 1.0
        sortino_ratio = (avg_trade / downside_dev * np.sqrt(total_closed)) if downside_dev > 0 else 0.0

        # Max Drawdown & Stagnation Calculation
        equities = [e["equity"] for e in equity_curve]
        peak = initial_balance
        max_dd_val = 0.0
        max_dd_pct = 0.0
        
        for eq in equities:
            if eq > peak:
                peak = eq
            dd_val = peak - eq
            dd_pct = (dd_val / peak * 100) if peak > 0 else 0.0
            if dd_val > max_dd_val:
                max_dd_val = dd_val
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        calmar_ratio = ((net_profit / initial_balance * 100) / max_dd_pct) if max_dd_pct > 0 else 0.0
        recovery_factor = (net_profit / max_dd_val) if max_dd_val > 0 else 0.0

        # Concentration & Jackpot Risk Analysis
        sorted_profits = sorted(profits, reverse=True)
        top1_profit = sorted_profits[0] if sorted_profits else 0.0
        top5_profit = sum(sorted_profits[:5]) if len(sorted_profits) >= 5 else net_profit
        top5_pct = (top5_profit / net_profit * 100) if net_profit > 0 else 0.0
        is_jackpot_dependent = top5_pct > 45.0

        # Scientific Composite Score (0-100)
        score_pf = min(30.0, (profit_factor / 3.0) * 30.0)
        score_sortino = min(25.0, (sortino_ratio / 2.0) * 25.0)
        score_dd = max(0.0, 20.0 - (max_dd_pct * 0.8))
        score_quality = 0.0 if is_jackpot_dependent else 25.0
        scientific_score = round(score_pf + score_sortino + score_dd + score_quality, 2)

        return {
            "initial_balance": initial_balance,
            "final_balance": round(initial_balance + net_profit, 2),
            "net_profit": round(net_profit, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "expectancy": round(expectancy, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "recovery_factor": round(recovery_factor, 2),
            "max_drawdown_val": round(max_dd_val, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "total_trades": total_closed,
            "top1_trade": round(top1_profit, 2),
            "top5_concentration_pct": round(top5_pct, 2),
            "is_jackpot_dependent": is_jackpot_dependent,
            "scientific_score": scientific_score,
            "status_label": "VERIFIED" if scientific_score >= 80 else ("MODERATE" if scientific_score >= 60 else "HIGH RISK")
        }

    @staticmethod
    def _empty_metrics(initial_balance):
        return {
            "initial_balance": initial_balance, "final_balance": initial_balance,
            "net_profit": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0, "total_trades": 0, "scientific_score": 0.0, "status_label": "NO TRADES"
        }
