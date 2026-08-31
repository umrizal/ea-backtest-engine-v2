# ============================================================
# stage3_routes.py
# Pintarin Laboratorium EA – Stage 3 API
#
# Endpoints:
#   POST /api/walkforward
#   POST /api/montecarlo
#   POST /api/portfolio/compare
#   GET  /api/conditions/presets
#   POST /api/conditions/preview
#   POST /api/report/export
#
# Register:
#   from stage3_routes import register_stage3_routes
#   register_stage3_routes(app, bt_engine=bt_engine, ...)
# ============================================================

from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request


# Job store sederhana (in-memory)
_S3_JOBS: Dict[str, Dict] = {}
_S3_LOCK = threading.Lock()


def register_stage3_routes(
    app: Flask,
    bt_engine=None,
    sheet_sync=None,
):
    # ----------------------------------------------------------
    # Condition presets
    # ----------------------------------------------------------
    @app.route("/api/conditions/presets", methods=["GET"])
    def conditions_presets():
        try:
            from condition_builder import ConditionBuilder
            return jsonify({
                "success": True,
                "presets": ConditionBuilder.presets(),
                "fields": ConditionBuilder.available_fields(),
                "ops": ConditionBuilder.available_ops(),
            }), 200
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/conditions/preview", methods=["POST"])
    def conditions_preview():
        """
        Preview sinyal dari condition rules (tanpa full backtest).
        Body: { rules: {...}, symbol?, start_date?, end_date? }
        """
        try:
            from condition_builder import ConditionBuilder
            data = request.json or {}
            rules = data.get("rules") or {}
            builder = ConditionBuilder(rules)

            # Load sedikit data untuk preview
            if bt_engine is None:
                return jsonify({"success": False, "error": "Engine tidak tersedia"}), 503

            symbol = data.get("symbol", "XAUUSD")
            start = data.get("start_date", "2024-06-01")
            end = data.get("end_date", "2024-08-31")

            if hasattr(bt_engine, "load_tick_data"):
                df = bt_engine.load_tick_data(symbol, start, end)
            else:
                return jsonify({"success": False, "error": "load_tick_data tidak ada"}), 500

            if df is None or df.empty:
                return jsonify({"success": False, "error": "Data kosong"}), 400

            # Batasi 500 bar terakhir untuk preview cepat
            if len(df) > 500:
                df = df.iloc[-500:].reset_index(drop=True)

            signals = builder.generate_signals(df)
            buy_n = int((signals == 1).sum())
            sell_n = int((signals == -1).sum())

            return jsonify({
                "success": True,
                "bars": len(df),
                "buy_signals": buy_n,
                "sell_signals": sell_n,
                "sample": [
                    {
                        "t": str(df.iloc[i]["datetime"]) if "datetime" in df.columns else str(i),
                        "signal": int(signals[i]),
                    }
                    for i in range(max(0, len(signals) - 20), len(signals))
                    if signals[i] != 0
                ],
            }), 200
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ----------------------------------------------------------
    # Walk-Forward
    # ----------------------------------------------------------
    @app.route("/api/walkforward", methods=["POST"])
    def walkforward_run():
        try:
            from walkforward import WalkForwardOptimizer

            if bt_engine is None:
                return jsonify({"success": False, "error": "Engine tidak tersedia"}), 503

            data = request.json or {}
            base_params = {
                "mql5_code": data.get("code") or data.get("mql5_code", ""),
                "symbol": data.get("symbol", "XAUUSD"),
                "start_date": data.get("start_date", "2024-01-01"),
                "end_date": data.get("end_date", "2024-12-31"),
                "balance": float(data.get("balance") or data.get("initial_balance") or 10000),
                "lot": float(data.get("lot") or 0.1),
                "logic_override": data.get("logic_override") or data.get("editable") and {
                    "exit_rules": {
                        "tp": data["editable"].get("tp", 50),
                        "sl": data["editable"].get("sl", 30),
                    },
                    "lot_management": {
                        "base_lot": data["editable"].get("base_lot", 0.1),
                    },
                } or {},
            }

            if not base_params["mql5_code"]:
                return jsonify({"success": False, "error": "Kode MQL5 kosong"}), 400

            param_space = data.get("param_space") or {
                "tp": [30, 40, 50, 60, 80],
                "sl": [20, 30, 40, 50],
                "base_lot": [0.05, 0.1, 0.15],
            }

            job_id = str(uuid.uuid4())
            with _S3_LOCK:
                _S3_JOBS[job_id] = {
                    "type": "walkforward",
                    "status": "running",
                    "progress": 0,
                    "result": None,
                    "error": None,
                    "created_at": datetime.now().isoformat(),
                }

            def worker():
                try:
                    def prog(v):
                        with _S3_LOCK:
                            _S3_JOBS[job_id]["progress"] = v

                    wfo = WalkForwardOptimizer(bt_engine, progress_callback=prog)
                    result = wfo.run(
                        base_params,
                        param_space=param_space,
                        is_months=int(data.get("is_months") or 6),
                        oos_months=int(data.get("oos_months") or 2),
                        step_months=int(data.get("step_months") or 2),
                        max_trials_per_window=int(data.get("max_trials") or 12),
                    )
                    with _S3_LOCK:
                        _S3_JOBS[job_id]["status"] = "completed"
                        _S3_JOBS[job_id]["progress"] = 100
                        _S3_JOBS[job_id]["result"] = result
                except Exception as e:
                    with _S3_LOCK:
                        _S3_JOBS[job_id]["status"] = "failed"
                        _S3_JOBS[job_id]["error"] = str(e)
                        _S3_JOBS[job_id]["error_trace"] = traceback.format_exc()

            threading.Thread(target=worker, daemon=True).start()

            return jsonify({
                "success": True,
                "job_id": job_id,
                "message": "Walk-Forward job dimulai.",
            }), 200

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ----------------------------------------------------------
    # Monte Carlo
    # ----------------------------------------------------------
    @app.route("/api/montecarlo", methods=["POST"])
    def montecarlo_run():
        try:
            from walkforward import MonteCarloSimulator

            data = request.json or {}
            profits = data.get("trade_profits") or []

            # Alternatif: ambil dari job backtest sebelumnya
            if not profits and data.get("trades"):
                profits = [float(t.get("profit") or 0) for t in data["trades"]]

            if len(profits) < 5:
                return jsonify({
                    "success": False,
                    "error": "Minimal 5 trade profits diperlukan.",
                }), 400

            mc = MonteCarloSimulator(
                n_simulations=int(data.get("n_simulations") or 1000),
                seed=data.get("seed", 42),
            )
            result = mc.run(
                profits,
                initial_balance=float(data.get("balance") or 10000),
                method=data.get("method") or "shuffle",
            )
            return jsonify(result), 200

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ----------------------------------------------------------
    # Portfolio compare
    # ----------------------------------------------------------
    @app.route("/api/portfolio/compare", methods=["POST"])
    def portfolio_compare():
        try:
            from portfolio_compare import PortfolioComparator

            if bt_engine is None:
                return jsonify({"success": False, "error": "Engine tidak tersedia"}), 503

            data = request.json or {}
            items = data.get("items") or []
            if not items:
                return jsonify({"success": False, "error": "items kosong"}), 400

            job_id = str(uuid.uuid4())
            with _S3_LOCK:
                _S3_JOBS[job_id] = {
                    "type": "portfolio",
                    "status": "running",
                    "progress": 0,
                    "result": None,
                    "error": None,
                    "created_at": datetime.now().isoformat(),
                }

            def worker():
                try:
                    def prog(v):
                        with _S3_LOCK:
                            _S3_JOBS[job_id]["progress"] = v

                    comp = PortfolioComparator(bt_engine)
                    result = comp.compare(items, progress_callback=prog)
                    with _S3_LOCK:
                        _S3_JOBS[job_id]["status"] = "completed"
                        _S3_JOBS[job_id]["progress"] = 100
                        _S3_JOBS[job_id]["result"] = result
                except Exception as e:
                    with _S3_LOCK:
                        _S3_JOBS[job_id]["status"] = "failed"
                        _S3_JOBS[job_id]["error"] = str(e)

            threading.Thread(target=worker, daemon=True).start()

            return jsonify({
                "success": True,
                "job_id": job_id,
                "message": "Portfolio comparison dimulai.",
            }), 200

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # ----------------------------------------------------------
    # Job status (shared)
    # ----------------------------------------------------------
    @app.route("/api/stage3/status/<job_id>", methods=["GET"])
    def stage3_status(job_id):
        with _S3_LOCK:
            j = _S3_JOBS.get(job_id)
        if not j:
            return jsonify({"success": False, "message": "Job tidak ditemukan"}), 404
        return jsonify({
            "success": True,
            "job_id": job_id,
            "type": j.get("type"),
            "status": j["status"],
            "progress": j.get("progress", 0),
            "error": j.get("error"),
        }), 200

    @app.route("/api/stage3/result/<job_id>", methods=["GET"])
    def stage3_result(job_id):
        with _S3_LOCK:
            j = _S3_JOBS.get(job_id)
        if not j:
            return jsonify({"success": False, "message": "Job tidak ditemukan"}), 404
        if j["status"] != "completed":
            return jsonify({
                "success": False,
                "message": f"Belum selesai: {j['status']}",
                "progress": j.get("progress", 0),
            }), 400
        return jsonify({
            "success": True,
            "job_id": job_id,
            "type": j.get("type"),
            "result": j.get("result"),
        }), 200

    # ----------------------------------------------------------
    # Report export
    # ----------------------------------------------------------
    @app.route("/api/report/export", methods=["POST"])
    def report_export():
        try:
            from report_export import ReportExporter

            data = request.json or {}
            result = data.get("result") or data.get("report") or {}
            job_id = data.get("job_id") or str(uuid.uuid4())
            fmt = (data.get("format") or "html").lower()
            push_sheet = bool(data.get("push_sheet", False))

            if fmt == "json":
                content = ReportExporter.to_json(result)
                return jsonify({
                    "success": True,
                    "format": "json",
                    "content": content,
                }), 200

            # HTML
            html = ReportExporter.to_html(job_id, result)
            path = None
            try:
                path = ReportExporter.save_html(job_id, result)
            except Exception:
                pass

            if push_sheet:
                ReportExporter.push_to_sheet(result, sheet_sync)

            return jsonify({
                "success": True,
                "format": "html",
                "path": path,
                "html": html,
            }), 200

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    print(
        "[STAGE3] Routes registered: "
        "/api/walkforward, /api/montecarlo, /api/portfolio/compare, "
        "/api/conditions/*, /api/report/export, /api/stage3/*"
    )
