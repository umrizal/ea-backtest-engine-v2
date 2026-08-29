import random
from backtest_engine import BacktestEngine

class GeneticOptimizer:
    def __init__(self, tick_data_dir):
        self.engine = BacktestEngine(tick_data_dir)

    def optimize(self, base_params, param_bounds, pop_size=10, generations=3):
        population = []
        for _ in range(pop_size):
            individual = {k: random.randint(v[0], v[1]) if isinstance(v[0], int) else random.uniform(v[0], v[1]) for k, v in param_bounds.items()}
            population.append(individual)

        best_score = -float('inf')
        best_params = None

        for gen in range(generations):
            for ind in population:
                p = base_params.copy()
                p.update(ind)
                try:
                    res = self.engine.run(p)
                    score = res.get("sortino_ratio", 0) + res.get("profit_factor", 0)
                    if score > best_score:
                        best_score = score
                        best_params = ind
                except Exception:
                    continue

        return {"best_params": best_params, "best_fitness": round(best_score, 2)}
