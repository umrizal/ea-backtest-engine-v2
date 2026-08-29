# app.py
# Pintarin Laboratorium EA - Backend Flask Application

import os
import uuid
import threading
import traceback
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, send_from_directory
from flask_cors import CORS

from database import DatabaseManager
from backtest_engine import BacktestEngine
from portfolio_engine import PortfolioEngine
from optimizer import GeneticOptimizer
from ai_explainer import AIExplainer
from report_generator import ReportGenerator
from ea_live_simulator import LiveSimulator

# ============================================================
# CONFIGURATION
# ============================================================

APP_PORT = int(os.environ.get("PORT", 5001))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TICK_DATA_DIR = os.environ.get("TICK_DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Create directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TICK_DATA_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# ============================================================
# FLASK APP INITIALIZATION
# ============================================================

app = Flask(__name__, template_folder=TEMPLATES_DIR)
CORS(app)

# ============================================================
# INITIALIZE ENGINES
# ============================================================

db = DatabaseManager()
bt_engine = BacktestEngine(TICK_DATA_DIR)
portfolio_engine = PortfolioEngine(TICK_DATA_DIR)
optimizer = GeneticOptimizer(TICK_DATA_DIR)

# Live Simulator menggunakan instance BacktestEngine yang SAMA supaya
# AI analysis cache, symbol map, dan seluruh logic (indikator, signal,
# TP/SL/trailing/martingale) selalu sinkron 1:1 dengan Backtest Terminal.
live_simulator = LiveSimulator(TICK_DATA_DIR, engine=bt_engine)

# ============================================================
# JOB MANAGEMENT (In-Memory Storage)
# ============================================================

JOBS = {}
JOBS_LOCK = threading.Lock()

# Job storage terpisah untuk Live Simulator (payload lebih besar
# karena menyimpan data per-candle untuk playback).
SIM_JOBS = {}
SIM_JOBS_LOCK = threading.Lock()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_parquet_files_count():
    """Menghitung jumlah file parquet di directory data."""
    try:
        files = [f for f in os.listdir(TICK_DATA_DIR) if f.endswith(".parquet")]
        return len(files)
    except Exception:
        return 0


def get_parquet_files_list():
    """Mengambil daftar file parquet di directory data."""
    try:
        files = [f for f in os.listdir(TICK_DATA_DIR) if f.endswith(".parquet")]
        return sorted(files)
    except Exception:
        return []


# ============================================================
# ROUTES - MAIN PAGES
# ============================================================

@app.route("/")
def index():
    """Render halaman utama (index.html)."""
    return render_template("index.html")


@app.route("/health")
@app.route("/api/health")
def health():
    """Health check endpoint."""
    parquet_count = get_parquet_files_count()
    parquet_files = get_parquet_files_list()
    
    return jsonify({
        "success": True,
        "status": "running",
        "port": APP_PORT,
        "parquet_files_found": parquet_count,
        "parquet_files": parquet_files[:10],  # Limit to 10 files
        "timestamp": datetime.now().isoformat()
    }), 200


# ============================================================
# ROUTES - FILE UPLOAD
# ============================================================

@app.route("/api/upload-ea", methods=["POST"])
def upload_ea():
    """
    Upload file EA (.mq5, .ex5, .mq4, .ex4, .set, .json).
    Jika file .mq5, ekstrak kode MQL5 untuk ditampilkan.
    """
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "message": "File tidak ditemukan dalam request."
        }), 400
    
    file = request.files["file"]
    
    if not file or file.filename == "":
        return jsonify({
            "success": False,
            "message": "File kosong atau tidak valid."
        }), 400
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:6]
    safe_filename = f"{timestamp}_{unique_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Gagal menyimpan file: {str(e)}"
        }), 500
    
    # Extract EA name
    ea_name = os.path.splitext(file.filename)[0]
    
    # Extract MQL5 code if .mq5 file
    mql5_code = ""
    if file.filename.endswith(".mq5") or file.filename.endswith(".mq4"):
        try:
            with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                mql5_code = f.read()
        except Exception as e:
            print(f"File read error: {e}")
            mql5_code = ""
    
    return jsonify({
        "success": True,
        "message": "File EA berhasil diupload.",
        "ea_name": ea_name,
        "mql5_code": mql5_code,
        "file_path": save_path,
        "file_size": os.path.getsize(save_path)
    }), 200


# ============================================================
# ROUTES - BACKTEST
# ============================================================

@app.route("/api/run-backtest", methods=["POST"])
def run_backtest():
    """
    Jalankan backtest EA dengan parameter yang diberikan.
    Returns job_id untuk polling status.
    """
    body = request.get_json(force=True, silent=True) or {}
    
    # Validate required fields
    if not body.get("mql5_code"):
        return jsonify({
            "success": False,
            "message": "Kode MQL5 tidak ditemukan. Harap paste kode atau upload file EA."
        }), 400
    
    if not body.get("symbol"):
        body["symbol"] = "XAUUSD"
    
    if not body.get("start_date"):
        body["start_date"] = "2024-01-01"
    
    if not body.get("end_date"):
        body["end_date"] = "2024-12-31"
    
    if not body.get("balance"):
        body["balance"] = 10000.0
    
    if not body.get("lot"):
        body["lot"] = 0.1
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job in memory
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "queued",
            "progress": 0,
            "params": body,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None
        }
    
    # Start background worker thread
    def worker():
        try:
            # Update status to running
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "running"
                JOBS[job_id]["progress"] = 10
                JOBS[job_id]["started_at"] = datetime.now().isoformat()
            
            # Progress callback
            def progress_cb(val):
                with JOBS_LOCK:
                    JOBS[job_id]["progress"] = min(100, val)
            
            # Run backtest
            res = bt_engine.run(body, progress_callback=progress_cb)
            
            # Save to database
            try:
                db.save_run(job_id, body, res)
            except Exception as db_err:
                print(f"Database save error: {db_err}")
            
            # Update status to completed
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["result"] = res
                JOBS[job_id]["completed_at"] = datetime.now().isoformat()
                
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Backtest error: {error_trace}")
            
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["error"] = str(e)
                JOBS[job_id]["error_trace"] = error_trace
                JOBS[job_id]["completed_at"] = datetime.now().isoformat()
    
    # Start thread
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Backtest job dimulai.",
        "job_id": job_id,
        "estimated_time": "30-60 detik"
    }), 200


@app.route("/api/backtest-status/<job_id>", methods=["GET"])
def backtest_status(job_id):
    """
    Cek status backtest job.
    """
    with JOBS_LOCK:
        j = JOBS.get(job_id)
    
    if not j:
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "error": j.get("error"),
        "created_at": j.get("created_at"),
        "started_at": j.get("started_at"),
        "completed_at": j.get("completed_at")
    }), 200


@app.route("/api/backtest-result/<job_id>", methods=["GET"])
def backtest_result(job_id):
    """
    Ambil hasil backtest setelah selesai.
    """
    with JOBS_LOCK:
        j = JOBS.get(job_id)
    
    if not j:
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404
    
    if j["status"] != "completed":
        return jsonify({
            "success": False,
            "message": f"Backtest belum selesai. Status: {j['status']}"
        }), 400
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "data": j.get("result"),
        "params": j.get("params")
    }), 200


@app.route("/api/backtest-cancel/<job_id>", methods=["POST"])
def backtest_cancel(job_id):
    """
    Batalkan backtest job (jika masih queued/running).
    """
    with JOBS_LOCK:
        j = JOBS.get(job_id)
    
    if not j:
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404
    
    if j["status"] in ["completed", "failed"]:
        return jsonify({
            "success": False,
            "message": f"Job sudah selesai dengan status: {j['status']}"
        }), 400
    
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "cancelled"
        JOBS[job_id]["progress"] = 0
    
    return jsonify({
        "success": True,
        "message": "Backtest job dibatalkan."
    }), 200


# ============================================================
# ROUTES - LIVE SIMULATOR (MT5 Strategy Tester "Visual Mode" style)
# ============================================================

@app.route("/api/simulate/run", methods=["POST"])
def simulate_run():
    """
    Menjalankan Live Simulator: menghasilkan data candle-by-candle
    (OHLC + indikator dinamis hasil AI Explainer + equity per-candle)
    yang siap di-playback frame demi frame di frontend, mirip MT5
    Strategy Tester visual mode. Menggunakan logic yang SAMA persis
    dengan Backtest Terminal (via BacktestEngine), jadi hasil akhirnya
    selalu konsisten.
    """
    body = request.get_json(force=True, silent=True) or {}

    if not body.get("mql5_code"):
        return jsonify({
            "success": False,
            "message": "Kode MQL5 tidak ditemukan. Harap paste kode atau upload file EA."
        }), 400

    body.setdefault("symbol", "XAUUSD")
    body.setdefault("start_date", "2024-01-01")
    body.setdefault("end_date", "2024-12-31")
    body.setdefault("balance", 10000.0)
    body.setdefault("lot", 0.1)
    # Batasi jumlah candle default supaya payload JSON tetap ringan
    # untuk playback di browser. Bisa dioverride dari frontend.
    body.setdefault("max_rows", 3000)

    job_id = str(uuid.uuid4())

    with SIM_JOBS_LOCK:
        SIM_JOBS[job_id] = {
            "status": "queued",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
        }

    def worker():
        try:
            with SIM_JOBS_LOCK:
                SIM_JOBS[job_id]["status"] = "running"

            def progress_cb(val):
                with SIM_JOBS_LOCK:
                    SIM_JOBS[job_id]["progress"] = min(100, val)

            res = live_simulator.build(body, progress_callback=progress_cb)

            with SIM_JOBS_LOCK:
                SIM_JOBS[job_id]["status"] = "completed"
                SIM_JOBS[job_id]["progress"] = 100
                SIM_JOBS[job_id]["result"] = res

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Live Simulator error: {error_trace}")

            with SIM_JOBS_LOCK:
                SIM_JOBS[job_id]["status"] = "failed"
                SIM_JOBS[job_id]["error"] = str(e)

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()

    return jsonify({
        "success": True,
        "message": "Live simulator job dimulai.",
        "job_id": job_id
    }), 200


@app.route("/api/simulate/status/<job_id>", methods=["GET"])
def simulate_status(job_id):
    """
    Cek status job Live Simulator.
    """
    with SIM_JOBS_LOCK:
        j = SIM_JOBS.get(job_id)

    if not j:
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404

    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "error": j.get("error")
    }), 200


@app.route("/api/simulate/data/<job_id>", methods=["GET"])
def simulate_data(job_id):
    """
    Ambil seluruh data frame Live Simulator (candle + indikator +
    equity per-candle) setelah job selesai, untuk di-playback di
    frontend.
    """
    with SIM_JOBS_LOCK:
        j = SIM_JOBS.get(job_id)

    if not j:
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404

    if j["status"] != "completed":
        return jsonify({
            "success": False,
            "message": f"Simulasi belum selesai. Status: {j['status']}"
        }), 400

    return jsonify({
        "success": True,
        "job_id": job_id,
        "data": j.get("result")
    }), 200


# ============================================================
# ROUTES - AI EXPLAINER
# ============================================================

@app.route("/api/explain-ea", methods=["POST"])
def explain_ea():
    """
    Analisis dan jelaskan logika EA MQL5 menggunakan AI.
    """
    body = request.get_json(force=True, silent=True) or {}
    mql5_code = body.get("mql5_code", "")
    
    if not mql5_code or not mql5_code.strip():
        return jsonify({
            "success": False,
            "message": "Kode MQL5 kosong. Harap paste kode atau upload file EA."
        }), 400
    
    try:
        explanation = AIExplainer.explain_ea(mql5_code)
        
        return jsonify({
            "success": True,
            "explanation": explanation,
            "code_length": len(mql5_code),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"AI Explainer error: {error_trace}")
        
        return jsonify({
            "success": False,
            "message": f"Error menganalisis EA: {str(e)}",
            "error_type": type(e).__name__
        }), 500


# ============================================================
# ROUTES - REPORT
# ============================================================

@app.route("/api/report/<job_id>", methods=["GET"])
def get_report(job_id):
    """
    Generate dan tampilkan HTML report hasil backtest.
    """
    with JOBS_LOCK:
        j = JOBS.get(job_id)
    
    if not j or not j.get("result"):
        return jsonify({
            "success": False,
            "message": "Report tidak ditemukan. Pastikan backtest sudah selesai."
        }), 404
    
    try:
        html_content = ReportGenerator.generate_html_report(job_id, j["result"], j.get("params", {}))
        return Response(html_content, mimetype="text/html")
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error generating report: {str(e)}"
        }), 500


@app.route("/api/report/<job_id>/download", methods=["GET"])
def download_report(job_id):
    """
    Download HTML report sebagai file.
    """
    with JOBS_LOCK:
        j = JOBS.get(job_id)
    
    if not j or not j.get("result"):
        return jsonify({
            "success": False,
            "message": "Report tidak ditemukan."
        }), 404
    
    try:
        html_content = ReportGenerator.generate_html_report(job_id, j["result"], j.get("params", {}))
        
        # Save to temp file
        report_filename = f"report_{job_id[:8]}.html"
        report_path = os.path.join(UPLOAD_DIR, report_filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return send_from_directory(UPLOAD_DIR, report_filename, as_attachment=True)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error downloading report: {str(e)}"
        }), 500


# ============================================================
# ROUTES - HISTORY / LEADERBOARD
# ============================================================

@app.route("/api/history", methods=["GET"])
def get_history():
    """
    Ambil histori backtest dari database.
    """
    limit = request.args.get("limit", 50, type=int)
    
    try:
        history = db.get_history(limit=limit)
        
        return jsonify({
            "success": True,
            "history": history,
            "count": len(history),
            "limit": limit
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error mengambil histori: {str(e)}"
        }), 500


@app.route("/api/history/<job_id>", methods=["GET"])
def get_history_detail(job_id):
    """
    Ambil detail histori backtest berdasarkan job_id.
    """
    try:
        # Get from in-memory jobs first
        with JOBS_LOCK:
            j = JOBS.get(job_id)
        
        if j and j.get("result"):
            return jsonify({
                "success": True,
                "data": j["result"],
                "params": j.get("params"),
                "from_cache": True
            }), 200
        
        # Get from database
        history = db.get_history(limit=1000)
        for record in history:
            if record.get("job_id") == job_id:
                return jsonify({
                    "success": True,
                    "data": record,
                    "from_cache": False
                }), 200
        
        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan di database."
        }), 404
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error mengambil detail: {str(e)}"
        }), 500


@app.route("/api/history/clear", methods=["POST"])
def clear_history():
    """
    Hapus semua histori backtest dari database.
    WARNING: Ini irreversible!
    """
    try:
        # Clear in-memory jobs
        with JOBS_LOCK:
            JOBS.clear()
        
        # Clear database (implement in database.py if needed)
        # For now, just return success
        
        return jsonify({
            "success": True,
            "message": "Histori backtest berhasil dihapus."
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error menghapus histori: {str(e)}"
        }), 500


# ============================================================
# ROUTES - PORTFOLIO (Optional)
# ============================================================

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    """
    Ambil ringkasan portfolio dari semua backtest.
    """
    try:
        history = db.get_history(limit=1000)
        
        if not history:
            return jsonify({
                "success": True,
                "portfolio": {
                    "total_runs": 0,
                    "total_profit": 0,
                    "avg_profit": 0,
                    "win_rate": 0,
                    "best_ea": None,
                    "worst_ea": None
                }
            }), 200
        
        # Calculate portfolio metrics
        total_runs = len(history)
        total_profit = sum(r.get("net_profit", 0) for r in history)
        avg_profit = total_profit / total_runs if total_runs > 0 else 0
        
        winning_runs = [r for r in history if r.get("net_profit", 0) > 0]
        win_rate = (len(winning_runs) / total_runs * 100) if total_runs > 0 else 0
        
        best_ea = max(history, key=lambda x: x.get("net_profit", 0)) if history else None
        worst_ea = min(history, key=lambda x: x.get("net_profit", 0)) if history else None
        
        return jsonify({
            "success": True,
            "portfolio": {
                "total_runs": total_runs,
                "total_profit": round(total_profit, 2),
                "avg_profit": round(avg_profit, 2),
                "win_rate": round(win_rate, 2),
                "best_ea": {
                    "name": best_ea.get("ea_name") if best_ea else None,
                    "profit": best_ea.get("net_profit") if best_ea else 0
                },
                "worst_ea": {
                    "name": worst_ea.get("ea_name") if worst_ea else None,
                    "profit": worst_ea.get("net_profit") if worst_ea else 0
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error menghitung portfolio: {str(e)}"
        }), 500


# ============================================================
# ROUTES - DATA FILES INFO
# ============================================================

@app.route("/api/data-files", methods=["GET"])
def get_data_files():
    """
    Ambil informasi file data parquet yang tersedia.
    """
    try:
        files = get_parquet_files_list()
        
        # Group by symbol
        symbols = {}
        for f in files:
            # Extract symbol from filename (e.g., XAUUSD_2024.parquet)
            parts = f.replace(".parquet", "").split("_")
            symbol = parts[0] if parts else "UNKNOWN"
            
            if symbol not in symbols:
                symbols[symbol] = []
            symbols[symbol].append(f)
        
        return jsonify({
            "success": True,
            "total_files": len(files),
            "files": files,
            "symbols": symbols,
            "data_directory": TICK_DATA_DIR
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error membaca data files: {str(e)}"
        }), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "Endpoint tidak ditemukan."
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Error internal server."
    }), 500


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "message": "Method tidak diizinkan."
    }), 405

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI # library nya tetap pakai openai
import os

app = Flask(__name__)
CORS(app)

# INI KUNCINYA: PAKAI BASE_URL FLaz
client = OpenAI(
    api_key=os.getenv("FLAZ_API_KEY"),
    base_url="https://ai.flaz.id/v1" # <-- ini provider flaz
)

@app.route('/api/bedah-logika', methods=['POST'])
def bedah_logika():
    try:
        data = request.get_json()
        code = data.get('code', '').strip()

        if not code:
            return jsonify({"success": False, "message": "Kode MQL5 kosong"}), 400

        prompt = f"Kamu adalah senior MQL5 developer. Bedah logika EA berikut ini secara detail, jelaskan fungsi, alur, dan risiko nya:\n\n```mql5\n{code}\n```"

        response = client.chat.completions.create(
            model="gpt-5.4-nano", # model dari flaz
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3
        )

        result = response.choices[0].message.content
        return jsonify({"success": True, "result": result})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PINTARIN LABORATORIUM EA - BACKEND SERVER")
    print("=" * 60)
    print(f"Port: {APP_PORT}")
    print(f"Data Directory: {TICK_DATA_DIR}")
    print(f"Upload Directory: {UPLOAD_DIR}")
    print(f"Templates Directory: {TEMPLATES_DIR}")
    print(f"Parquet Files Found: {get_parquet_files_count()}")
    print("=" * 60)
    print("Starting Flask server...")
    print("=" * 60)
    
    app.run(
        host="0.0.0.0",
        port=APP_PORT,
        debug=False,
        threaded=True
    )