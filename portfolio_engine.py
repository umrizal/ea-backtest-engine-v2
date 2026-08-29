import concurrent.futures
from backtest_engine import BacktestEngine

class PortfolioEngine:
    def __init__(self, tick_data_dir):
        self.tick_data_dir = tick_data_dir
        self.engine = BacktestEngine(tick_data_dir)

    def run_portfolio(self, symbols_list, base_params):
        results = {}
        combined_equity = []
        total_net_profit = 0.0

        def run_single(sym):
            p = base_params.copy()
            p["symbol"] = sym
            return sym, self.engine.run(p)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(symbols_list)) as executor:
            futures = [executor.submit(run_single, sym) for sym in symbols_list]
            for f in concurrent.futures.as_completed(futures):
                sym, res = f.result()
                results[sym] = res
                total_net_profit += res.get("net_profit", 0.0)

        return {
            "portfolio_net_profit": round(total_net_profit, 2),
            "symbols_breakdown": results
        }
