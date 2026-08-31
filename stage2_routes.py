# ============================================================
# stage2_routes.py
# Pintarin Laboratorium EA - Stage 2
#
# Endpoint baru yang ditambahkan ke app.py:
#   POST /api/parse-ea          → structured trading_logic
#   POST /api/explain-and-parse → teks + structured sekaligus
#   GET  /api/analytics-schema  → skema metrik untuk frontend
#
# Cara pakai:
#   dari app.py:
#       from stage2_routes import register_stage2_routes
#       register_stage2_routes(app, ai_explainer=ai_explainer)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Flask, jsonify, request


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _enrich_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menambah field tampilan untuk frontend:
    - status_color, status_emoji
    - risk_label
    - score_breakdown
    """
    if not metrics:
        return {}

    score = _safe_float(metrics.get("scientific_score"), 0)
    status = str(metrics.get("status_label", "NO TRADES")).upper()

    if score >= 80 or status == "VERIFIED":
        color, emoji = "#10b981", "✅"
    elif score >= 60 or status == "MODERATE":
        color, emoji = "#f59e0b", "⚠️"
    else:
        color, emoji = "#f43f5e", "🔴"

    is_jackpot = bool(metrics.get("is_jackpot_dependent", False))
    top5 = _safe_float(metrics.get("top5_concentration_pct"), 0)

    return {
        **metrics,
        "status_color": color,
        "status_emoji": emoji,
        "risk_label": "JACKPOT DEPENDENT" if is_jackpot else "DISTRIBUTED",
        "risk_warning": (
            f"Top-5 trade menyumbang {top5:.1f}% profit. Strategi rawan overfitting."
            if is_jackpot
            else None
        ),
        "score_breakdown": {
            "profit_factor_weight": 30,
            "sortino_weight": 25,
            "drawdown_weight": 20,
            "quality_weight": 25,
            "total": score,
        },
    }


def register_stage2_routes(
    app: Flask,
    ai_explainer=None,
    bt_engine=None,
):
    """Daftarkan semua route Stage 2 ke Flask app."""

    # ----------------------------------------------------------
    # POST /api/parse-ea
    # ----------------------------------------------------------
    @app.route("/api/parse-ea", methods=["POST"])
    def parse_ea():
        """
        Input : { "code" | "mql5_code": "...", "file_name": "..." }
        Output: structured trading_logic + parameter yang bisa diedit UI
        """
        try:
            data = request.json or {}
            code = data.get("code") or data.get("mql5_code", "")
            file_name = data.get("file_name", "Expert Advisor")

            if not code or not str(code).strip():
                return jsonify({
                    "success": False,
                    "error": "Kode MQL5 / EA tidak boleh kosong.",
                }), 400

            if ai_explainer is None:
                return jsonify({
                    "success": False,
                    "error": "AI Explainer tidak tersedia.",
                }), 503

            # Structured analysis
            if hasattr(ai_explainer, "analyze_structured"):
                logic = ai_explainer.analyze_structured(code, file_name)
            else:
                # fallback
                text = ai_explainer.explain_ea(code)
                logic = {
                    "strategy_type": "ma_crossover",
                    "explanation_raw": text,
                    "exit_rules": {"tp": 50, "sl": 30},
                    "lot_management": {"base_lot": 0.1, "martingale": False},
                }

            # Bentuk payload yang ramah frontend (editable fields)
            editable = {
                "strategy_type": logic.get("strategy_type", "ma_crossover"),
                "tp": logic.get("exit_rules", {}).get("tp", 50),
                "sl": logic.get("exit_rules", {}).get("sl", 30),
                "trailing": logic.get("exit_rules", {}).get("trailing", 0),
                "breakeven": logic.get("exit_rules", {}).get("breakeven", 0),
                "base_lot": logic.get("lot_management", {}).get("base_lot", 0.1),
                "multiplier": logic.get("lot_management", {}).get("multiplier", 1.0),
                "martingale": logic.get("lot_management", {}).get("martingale", False),
                "max_positions": logic.get("risk_management", {}).get("max_positions", 1),
                "max_lot": logic.get("lot_management", {}).get("max_lot", 100),
            }

            summary = logic.get("summary") or {}
            indicators = logic.get("indicators") or []

            return jsonify({
                "success": True,
                "trading_logic": logic,
                "editable": editable,
                "summary": {
                    "name": summary.get("name"),
                    "description": summary.get("description"),
                    "timeframe": summary.get("timeframe"),
                    "pair": summary.get("pair"),
                    "strategy_type": logic.get("strategy_type"),
                    "indicator_count": len(indicators),
                    "indicators": [
                        i.get("name") if isinstance(i, dict) else str(i)
                        for i in indicators
                    ],
                },
                "bugs": logic.get("bugs") or [],
                "risks": logic.get("risks") or [],
            }), 200

        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    # ----------------------------------------------------------
    # POST /api/explain-and-parse
    # ----------------------------------------------------------
    @app.route("/api/explain-and-parse", methods=["POST"])
    def explain_and_parse():
        """
        Sekaligus: teks penjelasan (UI) + structured logic (engine).
        Hemat 1 round-trip dari frontend.
        """
        try:
            data = request.json or {}
            code = data.get("code") or data.get("mql5_code", "")
            file_name = data.get("file_name", "Expert Advisor")

            if not code or not str(code).strip():
                return jsonify({
                    "success": False,
                    "error": "Kode MQL5 / EA tidak boleh kosong.",
                    "explanation": "❌ Kode MQL5 / EA tidak boleh kosong.",
                }), 200

            if ai_explainer is None:
                return jsonify({
                    "success": False,
                    "error": "AI Explainer tidak tersedia.",
                }), 503

            # Teks
            explanation = ai_explainer.explain_ea(code, file_name)
            is_error = isinstance(explanation, str) and (
                explanation.startswith("❌") or explanation.startswith("⚠️")
            )

            # Structured
            logic = {}
            editable = {}
            if not is_error and hasattr(ai_explainer, "analyze_structured"):
                logic = ai_explainer.analyze_structured(code, file_name)
                editable = {
                    "strategy_type": logic.get("strategy_type", "ma_crossover"),
                    "tp": logic.get("exit_rules", {}).get("tp", 50),
                    "sl": logic.get("exit_rules", {}).get("sl", 30),
                    "trailing": logic.get("exit_rules", {}).get("trailing", 0),
                    "breakeven": logic.get("exit_rules", {}).get("breakeven", 0),
                    "base_lot": logic.get("lot_management", {}).get("base_lot", 0.1),
                    "multiplier": logic.get("lot_management", {}).get("multiplier", 1.0),
                    "martingale": bool(logic.get("lot_management", {}).get("martingale", False)),
                    "max_positions": logic.get("risk_management", {}).get("max_positions", 1),
                    "max_lot": logic.get("lot_management", {}).get("max_lot", 100),
                }

            return jsonify({
                "success": not is_error,
                "explanation": explanation,
                "trading_logic": logic,
                "editable": editable,
                "error": explanation if is_error else None,
            }), 200

        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "explanation": f"❌ Error: {e}",
            }), 200

    # ----------------------------------------------------------
    # POST /api/run-backtest-with-params
    # ----------------------------------------------------------
    @app.route("/api/run-backtest-with-params", methods=["POST"])
    def run_backtest_with_params():
        """
        Backtest dengan parameter yang sudah di-edit user dari panel Stage 2.
        Body:
          {
            "code": "...",
            "editable": { tp, sl, base_lot, ... },
            "symbol": "XAUUSD",
            "start_date": "...",
            "end_date": "...",
            "balance": 10000
          }
        """
        try:
            data = request.json or {}
            mql5_code = data.get("code") or data.get("mql5_code", "")
            editable = data.get("editable") or {}

            if not mql5_code or not str(mql5_code).strip():
                return jsonify({
                    "success": False,
                    "error": "Kode MQL5 tidak ditemukan.",
                }), 400

            if bt_engine is None:
                return jsonify({
                    "success": False,
                    "error": "BacktestEngine tidak tersedia.",
                }), 503

            # Bangun override logic dari editable
            override = {
                "exit_rules": {
                    "tp": _safe_float(editable.get("tp"), 50),
                    "sl": _safe_float(editable.get("sl"), 30),
                    "trailing": _safe_float(editable.get("trailing"), 0),
                    "breakeven": _safe_float(editable.get("breakeven"), 0),
                    "tp_unit": "pips",
                    "sl_unit": "pips",
                },
                "lot_management": {
                    "base_lot": _safe_float(editable.get("base_lot"), 0.1),
                    "multiplier": _safe_float(editable.get("multiplier"), 1.0),
                    "martingale": bool(editable.get("martingale", False)),
                    "max_lot": _safe_float(editable.get("max_lot"), 100),
                    "type": "martingale" if editable.get("martingale") else "fixed",
                },
                "risk_management": {
                    "max_positions": int(editable.get("max_positions") or 1),
                },
            }
            if editable.get("strategy_type"):
                override["strategy_type"] = str(editable["strategy_type"]).lower()

            body = {
                "mql5_code": mql5_code,
                "symbol": data.get("symbol", "XAUUSD"),
                "start_date": data.get("start_date", "2024-01-01"),
                "end_date": data.get("end_date", "2024-12-31"),
                "balance": _safe_float(data.get("balance") or data.get("initial_balance"), 10000),
                "lot": _safe_float(editable.get("base_lot"), 0.1),
                "logic_override": override,
                "ea_name": data.get("ea_name", "EA_MQL5"),
            }

            # Jalankan (sinkron untuk simplicity; production bisa pakai job queue)
            if hasattr(bt_engine, "run"):
                result = bt_engine.run(body)
            elif hasattr(bt_engine, "run_backtest"):
                result = bt_engine.run_backtest(
                    mql5_code=mql5_code,
                    initial_balance=body["balance"],
                    start_date=body["start_date"],
                    end_date=body["end_date"],
                )
            else:
                return jsonify({
                    "success": False,
                    "error": "Method run tidak ditemukan pada BacktestEngine.",
                }), 500

            # Enrich metrics untuk UI
            metrics = result.get("metrics") or result.get("report") or result
            if isinstance(metrics, dict):
                enriched = _enrich_metrics(metrics)
                if "metrics" in result:
                    result["metrics"] = enriched
                else:
                    result = {**result, **enriched} if isinstance(result, dict) else enriched

            return jsonify({
                "success": True,
                "report": result,
                "data": result,
                "override_used": override,
            }), 200

        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    # ----------------------------------------------------------
    # GET /api/analytics-schema
    # ----------------------------------------------------------
    @app.route("/api/analytics-schema", methods=["GET"])
    def analytics_schema():
        """Skema metrik yang ditampilkan di dashboard (dokumentasi frontend)."""
        return jsonify({
            "success": True,
            "kpis": [
                {"key": "net_profit", "label": "Net Profit", "format": "money"},
                {"key": "profit_factor", "label": "Profit Factor", "format": "number2"},
                {"key": "win_rate", "label": "Win Rate", "format": "percent"},
                {"key": "sortino_ratio", "label": "Sortino Ratio", "format": "number2"},
                {"key": "max_drawdown_pct", "label": "Max Drawdown", "format": "percent"},
                {"key": "expectancy", "label": "Expectancy", "format": "money"},
                {"key": "scientific_score", "label": "Scientific Score", "format": "score"},
                {"key": "total_trades", "label": "Total Trades", "format": "int"},
                {"key": "recovery_factor", "label": "Recovery Factor", "format": "number2"},
                {"key": "calmar_ratio", "label": "Calmar Ratio", "format": "number2"},
            ],
            "risk_flags": [
                "is_jackpot_dependent",
                "top5_concentration_pct",
                "status_label",
            ],
        }), 200

    print("[STAGE2] Routes registered: /api/parse-ea, /api/explain-and-parse, /api/run-backtest-with-params, /api/analytics-schema")
