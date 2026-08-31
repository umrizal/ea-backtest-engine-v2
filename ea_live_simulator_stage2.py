# ============================================================
# ea_live_simulator_stage2.py
# Pintarin Laboratorium EA – Stage 2 enhancement
#
# Drop-in replacement / patch untuk ea_live_simulator.py
# Perbaikan:
#   - Overlay lebih lengkap per strategy_type
#   - Oscillator panel untuk RSI/MACD/Stoch selalu tersedia
#     jika kolom indikator ada di DataFrame
#   - Meta result memuat scientific-ready fields
#
# Cara pakai:
#   Ganti import di app.py:
#     from ea_live_simulator_stage2 import LiveSimulator
#   ATAU copy isi class ke file asli.
# ============================================================

import numpy as np
import pandas as pd

from backtest_engine import BacktestEngine


class LiveSimulator:
    """
    Live Simulator (MT5 Strategy Tester Visual Mode style)
    Sinkron dengan BacktestEngine + AI structured logic (Stage 1/2).
    """

    VERSION = "2.0.0-stage2"

    STRATEGY_OVERLAYS = {
        "ma_crossover": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "trend_following": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "scalping": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "grid": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "martingale": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "bollinger": [
            ("bb_upper", "BB Upper"),
            ("bb_middle", "BB Mid"),
            ("bb_lower", "BB Lower"),
        ],
        "alligator": [("ma_fast", "Lips"), ("ma_slow", "Jaw")],
        "breakout": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "price_action": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "rsi": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "macd": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "stochastic": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "fractal": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
        "other": [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")],
    }

    STRATEGY_OSCILLATOR = {
        "rsi": ("rsi", "RSI"),
        "macd": ("macd", "MACD"),
        "stochastic": ("stoch_k", "Stoch %K"),
        "trend_following": ("rsi", "RSI"),
        "scalping": ("rsi", "RSI"),
    }

    def __init__(self, tick_data_dir="data", engine=None):
        self.engine = engine or BacktestEngine(tick_data_dir)

    def build(self, params, progress_callback=None):
        engine = self.engine

        raw_symbol = params.get("symbol", "XAUUSD")
        symbol_clean = engine._clean_symbol(raw_symbol)
        start_date = params.get("start_date", "2024-01-01")
        end_date = params.get("end_date", "2024-12-31")
        initial_balance = float(params.get("balance", 10000.0))
        base_lot = float(params.get("lot", 0.1))
        mql5_code = params.get("mql5_code", "")

        def prog(v):
            engine._progress(progress_callback, v)

        prog(5)

        # AI analysis (structured)
        trading_logic = engine._analyze_mql5_code(mql5_code)

        # Apply logic_override dari Stage 2 parameter panel (jika ada)
        override = params.get("logic_override") or {}
        if override:
            for key in ("exit_rules", "lot_management", "risk_management"):
                if key in override and isinstance(override[key], dict):
                    trading_logic[key] = {
                        **trading_logic.get(key, {}),
                        **override[key],
                    }
            if "strategy_type" in override:
                trading_logic["strategy_type"] = override["strategy_type"]

        prog(15)

        df = engine.load_tick_data(raw_symbol, start_date, end_date)
        if df.empty:
            raise FileNotFoundError(
                f"Tidak ada data broker untuk {raw_symbol} "
                f"periode {start_date} - {end_date}"
            )

        missing = engine._validate_ohlc(df)
        if missing:
            raise ValueError(f"Kolom OHLC tidak lengkap. Missing: {missing}")

        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=["open", "high", "low", "close", "datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)

        max_rows = int(params.get("max_rows", 3000))
        if max_rows > 0 and len(df) > max_rows:
            df = df.iloc[-max_rows:].reset_index(drop=True)

        prog(30)

        df = engine._calculate_indicators(df, trading_logic)
        signals = engine._generate_signals(df, trading_logic)
        df["_signal"] = signals
        prog(45)

        strategy = str(trading_logic.get("strategy_type", "ma_crossover")).lower()
        risk_params = trading_logic.get("exit_rules", {})
        lot_management = trading_logic.get("lot_management", {})
        risk_management = trading_logic.get("risk_management", {})

        max_positions = int(risk_management.get("max_positions", 1))
        is_grid = strategy in ("grid", "martingale")
        if not is_grid:
            max_positions = 1

        overlay_cols = self.STRATEGY_OVERLAYS.get(
            strategy, [("ma_fast", "MA Cepat"), ("ma_slow", "MA Lambat")]
        )
        overlay_cols = [(c, label) for c, label in overlay_cols if c in df.columns]

        osc_col = self.STRATEGY_OSCILLATOR.get(strategy)
        if osc_col and osc_col[0] not in df.columns:
            # fallback: cari oscillator yang tersedia
            for cand in (("rsi", "RSI"), ("macd", "MACD"), ("stoch_k", "Stoch %K")):
                if cand[0] in df.columns:
                    osc_col = cand
                    break
            else:
                osc_col = None

        balance = initial_balance
        equity = initial_balance
        current_lot = base_lot
        positions = []
        trades = []
        frames = []

        max_equity = initial_balance
        max_dd = 0.0
        total_rows = len(df)

        for i in range(total_rows):
            row = df.iloc[i]
            ts = row["datetime"]
            close_price = float(row["close"])

            floating = 0.0
            for pos in positions:
                floating += engine._calculate_profit(
                    symbol_clean,
                    pos["direction"],
                    pos["entry"],
                    close_price,
                    pos["lot"],
                )
            equity = balance + floating
            max_equity = max(max_equity, equity)
            if max_equity > 0:
                dd = (max_equity - equity) / max_equity * 100
                max_dd = max(max_dd, dd)

            closed_now = []
            for pos in list(positions):
                should_close, exit_price, reason = engine._check_position_exit(
                    pos, row, symbol_clean, risk_params
                )

                if not should_close:
                    opposite = (
                        (pos["direction"] == "BUY" and signals[i] == -1)
                        or (pos["direction"] == "SELL" and signals[i] == 1)
                    )
                    if opposite and risk_params.get("opposite_signal", False):
                        exit_price = engine._exit_price(
                            row, pos["direction"], close_price
                        )
                        should_close = True
                        reason = "Opposite Signal"

                if should_close:
                    balance, trade = engine._close_position(
                        pos, exit_price, ts, symbol_clean, reason, balance, params
                    )
                    trades.append(trade)
                    closed_now.append(pos)

                    if trade["profit"] < 0 and lot_management.get("martingale", False):
                        mult = float(lot_management.get("multiplier", 1.0))
                        max_lot = float(lot_management.get("max_lot", 100.0))
                        current_lot = min(current_lot * mult, max_lot)
                    else:
                        current_lot = base_lot

            for pos in closed_now:
                positions.remove(pos)

            signal = int(signals[i])
            opened_now = None

            can_open = (
                signal != 0
                and engine._time_allowed(ts, trading_logic)
                and engine._spread_allowed(row, trading_logic, symbol_clean)
                and len(positions) < max_positions
            )

            if can_open:
                direction = "BUY" if signal == 1 else "SELL"
                entry_price = engine._entry_price(row, direction, close_price)
                pos = engine._create_position(
                    symbol_clean,
                    direction,
                    entry_price,
                    ts,
                    current_lot,
                    risk_params,
                )
                positions.append(pos)
                opened_now = {
                    "direction": direction,
                    "price": round(entry_price, 5),
                }

            overlays = {}
            for col, label in overlay_cols:
                val = row.get(col)
                overlays[label] = None if pd.isna(val) else round(float(val), 6)

            osc_val = None
            if osc_col:
                v = row.get(osc_col[0])
                osc_val = None if pd.isna(v) else round(float(v), 4)

            frames.append(
                {
                    "t": str(ts),
                    "o": round(float(row["open"]), 6),
                    "h": round(float(row["high"]), 6),
                    "l": round(float(row["low"]), 6),
                    "c": round(float(row["close"]), 6),
                    "overlays": overlays,
                    "osc": osc_val,
                    "signal": signal,
                    "opened": opened_now,
                    "closed_count": len(closed_now),
                    "position": positions[-1]["direction"] if positions else None,
                    "balance": round(balance, 2),
                    "equity": round(equity, 2),
                    "drawdown": round(max_dd, 3),
                    "trades_total": len(trades),
                }
            )

            if progress_callback and total_rows > 0 and (
                i % max(1, total_rows // 50) == 0
            ):
                prog(45 + int((i / total_rows) * 45))

        if positions:
            last_row = df.iloc[-1]
            final_ts = last_row["datetime"]
            final_price = float(last_row["close"])

            for pos in list(positions):
                exit_price = engine._exit_price(
                    last_row, pos["direction"], final_price
                )
                balance, trade = engine._close_position(
                    pos,
                    exit_price,
                    final_ts,
                    symbol_clean,
                    "End of Simulation",
                    balance,
                    params,
                )
                trades.append(trade)

            positions = []
            if frames:
                frames[-1]["balance"] = round(balance, 2)
                frames[-1]["equity"] = round(balance, 2)
                frames[-1]["position"] = None
                frames[-1]["trades_total"] = len(trades)

        prog(98)

        overlay_labels = [label for _, label in overlay_cols]

        # Analytics singkat untuk meta
        from analytics import QuantitativeAnalytics

        equity_curve = [
            {"equity": f["equity"], "datetime": f["t"]} for f in frames
        ]
        metrics = QuantitativeAnalytics.calculate_metrics(
            initial_balance, trades, equity_curve
        )

        result = {
            "meta": {
                "ea_name": params.get("ea_name", "EA_MQL5"),
                "symbol": symbol_clean,
                "symbol_raw": raw_symbol,
                "strategy_type": strategy,
                "indicators": trading_logic.get("indicators", []),
                "overlay_labels": overlay_labels,
                "oscillator_label": osc_col[1] if osc_col else None,
                "initial_balance": initial_balance,
                "final_balance": round(balance, 2),
                "total_frames": len(frames),
                "total_trades": len(trades),
                "max_drawdown_pct": round(max_dd, 3),
                "engine_version": getattr(engine, "VERSION", "unknown"),
                "simulator_version": self.VERSION,
                "scientific_score": metrics.get("scientific_score"),
                "status_label": metrics.get("status_label"),
                "profit_factor": metrics.get("profit_factor"),
                "win_rate": metrics.get("win_rate"),
            },
            "frames": frames,
            "trades": trades,
            "metrics": metrics,
        }

        prog(100)
        return result
