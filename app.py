# ============================================================
# app.py
# Pintarin Laboratorium EA - Backend Flask Application
# ============================================================

import os
import uuid
import threading
import traceback
import time
from datetime import datetime

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    Response,
    send_from_directory
)
from flask_cors import CORS

from database import DatabaseManager
from backtest_engine import BacktestEngine
from portfolio_engine import PortfolioEngine
from optimizer import GeneticOptimizer
from ai_explainer import AIExplainer
from report_generator import ReportGenerator

# Live Simulator
try:
    from ea_live_simulator import LiveSimulator
    LIVE_SIMULATOR_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] LiveSimulator tidak tersedia: {e}")
    LiveSimulator = None
    LIVE_SIMULATOR_AVAILABLE = False


# ============================================================
# CONFIGURATION
# ============================================================

APP_PORT = int(os.environ.get("PORT", 5001))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TICK_DATA_DIR = os.environ.get(
    "TICK_DATA_DIR",
    os.path.join(BASE_DIR, "data")
)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TICK_DATA_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)


# ============================================================
# FLASK APP INITIALIZATION
# ============================================================

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR
)

CORS(app)


# ============================================================
# INITIALIZE ENGINES
# ============================================================

print("[INIT] Initializing DatabaseManager...")
db = DatabaseManager()

print("[INIT] Initializing BacktestEngine...")
bt_engine = BacktestEngine(TICK_DATA_DIR)

print("[INIT] Initializing PortfolioEngine...")
portfolio_engine = PortfolioEngine(TICK_DATA_DIR)

print("[INIT] Initializing GeneticOptimizer...")
optimizer = GeneticOptimizer(TICK_DATA_DIR)


# ============================================================
# AI EXPLAINER
#
# IMPORTANT:
# AIExplainer digunakan sebagai INSTANCE.
# Jangan gunakan:
#
#     AIExplainer.explain_ea(...)
#
# Gunakan:
#
#     ai_explainer.explain_ea(...)
# ============================================================

print("[INIT] Initializing AIExplainer...")

try:
    ai_explainer = AIExplainer()
    AI_EXPLAINER_AVAILABLE = True
    print("[INIT] AIExplainer initialized successfully.")
except Exception as e:
    ai_explainer = None
    AI_EXPLAINER_AVAILABLE = False
    print(f"[ERROR] AIExplainer initialization failed: {e}")
    traceback.print_exc()


# ============================================================
# LIVE SIMULATOR
# ============================================================

if LIVE_SIMULATOR_AVAILABLE:
    try:
        live_simulator = LiveSimulator(
            TICK_DATA_DIR,
            engine=bt_engine
        )

        print("[INIT] LiveSimulator initialized successfully.")

    except Exception as e:
        live_simulator = None
        LIVE_SIMULATOR_AVAILABLE = False

        print(f"[ERROR] LiveSimulator initialization failed: {e}")
        traceback.print_exc()
else:
    live_simulator = None


# ============================================================
# JOB MANAGEMENT
# ============================================================

JOBS = {}
JOBS_LOCK = threading.Lock()

SIM_JOBS = {}
SIM_JOBS_LOCK = threading.Lock()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_parquet_files_count():
    """Menghitung jumlah file parquet di directory data."""

    try:
        files = [
            f
            for f in os.listdir(TICK_DATA_DIR)
            if f.endswith(".parquet")
        ]

        return len(files)

    except Exception:
        return 0


def get_parquet_files_list():
    """Mengambil daftar file parquet di directory data."""

    try:
        files = [
            f
            for f in os.listdir(TICK_DATA_DIR)
            if f.endswith(".parquet")
        ]

        return sorted(files)

    except Exception:
        return []


def get_ai_status():
    """
    Mendapatkan status AI Explainer.
    """

    return {
        "available": AI_EXPLAINER_AVAILABLE,
        "initialized": ai_explainer is not None
    }


# ============================================================
# MAIN PAGE
# ============================================================

@app.route("/")
def index():
    """Render halaman utama."""

    return render_template("index.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
@app.route("/api/health")
def health():

    parquet_count = get_parquet_files_count()
    parquet_files = get_parquet_files_list()

    return jsonify({
        "success": True,
        "status": "running",

        "port": APP_PORT,

        "parquet_files_found": parquet_count,

        "parquet_files": parquet_files[:10],

        "ai_explainer": get_ai_status(),

        "live_simulator": {
            "available": LIVE_SIMULATOR_AVAILABLE,
            "initialized": live_simulator is not None
        },

        "timestamp": datetime.now().isoformat()
    }), 200


# ============================================================
# AI EXPLAINER HEALTH CHECK
# ============================================================

@app.route('/api/explain-ea', methods=['POST'])
def explain_ea():
    try:
        data = request.json or {}
        # Menerima baik field 'code' maupun 'mql5_code' dari frontend
        code = data.get('code') or data.get('mql5_code', '')

        if not code or not str(code).strip():
            return jsonify({
                "success": False,
                "error": "Kode MQL5 / EA tidak boleh kosong."
            }), 400

        result = ai_explainer.explain_ea(code)

        if isinstance(result, str) and (result.startswith("❌") or result.startswith("⚠️")):
            return jsonify({
                "success": False,
                "explanation": result,
                "result": result,
                "error": result
            }), 500

        return jsonify({
            "success": True,
            "explanation": result,
            "result": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
# ============================================================
# ROUTES - FILE UPLOAD
# ============================================================

@app.route("/api/upload-ea", methods=["POST"])
def upload_ea():

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

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    unique_id = str(uuid.uuid4())[:6]

    safe_filename = (
        f"{timestamp}_{unique_id}_{file.filename}"
    )

    save_path = os.path.join(
        UPLOAD_DIR,
        safe_filename
    )

    # ========================================================
    # SAVE FILE
    # ========================================================

    try:

        file.save(save_path)

    except Exception as e:

        return jsonify({
            "success": False,
            "message": (
                f"Gagal menyimpan file: {str(e)}"
            )
        }), 500

    # ========================================================
    # EA NAME
    # ========================================================

    ea_name = os.path.splitext(
        file.filename
    )[0]

    # ========================================================
    # READ MQL CODE
    # ========================================================

    mql5_code = ""

    filename_lower = file.filename.lower()

    if filename_lower.endswith(".mq5") or \
       filename_lower.endswith(".mq4"):

        try:

            with open(
                save_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:

                mql5_code = f.read()

        except Exception as e:

            print(
                f"[UPLOAD] File read error: {e}"
            )

            mql5_code = ""

    # ========================================================
    # RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "message": "File EA berhasil diupload.",

        "ea_name": ea_name,

        "mql5_code": mql5_code,

        "file_path": save_path,

        "file_size": os.path.getsize(
            save_path
        )

    }), 200


# ============================================================
# ROUTES - BACKTEST
# ============================================================

@app.route("/api/run-backtest", methods=["POST"])
def run_backtest():

    body = request.get_json(
        force=True,
        silent=True
    ) or {}

    # ========================================================
    # VALIDATION
    # ========================================================

    if not body.get("mql5_code"):

        return jsonify({
            "success": False,
            "message": (
                "Kode MQL5 tidak ditemukan. "
                "Harap paste kode atau upload file EA."
            )
        }), 400

    # ========================================================
    # DEFAULT PARAMS
    # ========================================================

    body.setdefault(
        "symbol",
        "XAUUSD"
    )

    body.setdefault(
        "start_date",
        "2024-01-01"
    )

    body.setdefault(
        "end_date",
        "2024-12-31"
    )

    body.setdefault(
        "balance",
        10000.0
    )

    body.setdefault(
        "lot",
        0.1
    )

    # ========================================================
    # JOB ID
    # ========================================================

    job_id = str(uuid.uuid4())

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

    # ========================================================
    # BACKGROUND WORKER
    # ========================================================

    def worker():

        try:

            with JOBS_LOCK:

                JOBS[job_id]["status"] = "running"

                JOBS[job_id]["progress"] = 10

                JOBS[job_id]["started_at"] = (
                    datetime.now().isoformat()
                )

            # ------------------------------------------------
            # PROGRESS CALLBACK
            # ------------------------------------------------

            def progress_cb(val):

                with JOBS_LOCK:

                    JOBS[job_id]["progress"] = min(
                        100,
                        val
                    )

            # ------------------------------------------------
            # RUN BACKTEST
            # ------------------------------------------------

            print(
                f"[BACKTEST] Starting job {job_id}"
            )

            res = bt_engine.run(
                body,
                progress_callback=progress_cb
            )

            # ------------------------------------------------
            # SAVE DATABASE
            # ------------------------------------------------

            try:

                db.save_run(
                    job_id,
                    body,
                    res
                )

            except Exception as db_err:

                print(
                    f"[DATABASE] Save error: {db_err}"
                )

            # ------------------------------------------------
            # COMPLETE
            # ------------------------------------------------

            with JOBS_LOCK:

                JOBS[job_id]["status"] = "completed"

                JOBS[job_id]["progress"] = 100

                JOBS[job_id]["result"] = res

                JOBS[job_id]["completed_at"] = (
                    datetime.now().isoformat()
                )

            print(
                f"[BACKTEST] Job {job_id} completed"
            )

        except Exception as e:

            error_trace = traceback.format_exc()

            print("=" * 70)
            print(f"[BACKTEST ERROR] Job {job_id}")
            print("=" * 70)
            print(error_trace)
            print("=" * 70)

            with JOBS_LOCK:

                JOBS[job_id]["status"] = "failed"

                JOBS[job_id]["error"] = str(e)

                JOBS[job_id]["error_trace"] = (
                    error_trace
                )

                JOBS[job_id]["completed_at"] = (
                    datetime.now().isoformat()
                )

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()

    return jsonify({

        "success": True,

        "message": "Backtest job dimulai.",

        "job_id": job_id,

        "estimated_time": "30-60 detik"

    }), 200


# ============================================================
# BACKTEST STATUS
# ============================================================

@app.route(
    "/api/backtest-status/<job_id>",
    methods=["GET"]
)
def backtest_status(job_id):

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


# ============================================================
# BACKTEST RESULT
# ============================================================

@app.route(
    "/api/backtest-result/<job_id>",
    methods=["GET"]
)
def backtest_result(job_id):

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
            "message": (
                f"Backtest belum selesai. "
                f"Status: {j['status']}"
            )
        }), 400

    return jsonify({

        "success": True,

        "job_id": job_id,

        "data": j.get("result"),

        "params": j.get("params")

    }), 200


# ============================================================
# BACKTEST CANCEL
# ============================================================

@app.route(
    "/api/backtest-cancel/<job_id>",
    methods=["POST"]
)
def backtest_cancel(job_id):

    with JOBS_LOCK:

        j = JOBS.get(job_id)

    if not j:

        return jsonify({
            "success": False,
            "message": "Job ID tidak ditemukan."
        }), 404

    if j["status"] in [
        "completed",
        "failed",
        "cancelled"
    ]:

        return jsonify({
            "success": False,
            "message": (
                f"Job sudah selesai dengan status: "
                f"{j['status']}"
            )
        }), 400

    with JOBS_LOCK:

        JOBS[job_id]["status"] = "cancelled"

        JOBS[job_id]["progress"] = 0

    return jsonify({

        "success": True,

        "message": "Backtest job dibatalkan."

    }), 200


# ============================================================
# ROUTES - LIVE SIMULATOR
# ============================================================

@app.route(
    "/api/simulate/run",
    methods=["POST"]
)
def simulate_run():

    if not LIVE_SIMULATOR_AVAILABLE or \
       live_simulator is None:

        return jsonify({
            "success": False,
            "message": "Live Simulator tidak tersedia."
        }), 503

    body = request.get_json(
        force=True,
        silent=True
    ) or {}

    if not body.get("mql5_code"):

        return jsonify({
            "success": False,
            "message": "Kode MQL5 tidak ditemukan."
        }), 400

    body.setdefault(
        "symbol",
        "XAUUSD"
    )

    body.setdefault(
        "start_date",
        "2024-01-01"
    )

    body.setdefault(
        "end_date",
        "2024-12-31"
    )

    body.setdefault(
        "balance",
        10000.0
    )

    body.setdefault(
        "lot",
        0.1
    )

    body.setdefault(
        "max_rows",
        3000
    )

    job_id = str(uuid.uuid4())

    with SIM_JOBS_LOCK:

        SIM_JOBS[job_id] = {

            "status": "queued",

            "progress": 0,

            "params": body,

            "result": None,

            "error": None,

            "created_at": datetime.now().isoformat()
        }

    def worker():

        try:

            with SIM_JOBS_LOCK:

                SIM_JOBS[job_id]["status"] = "running"

            def progress_cb(val):

                with SIM_JOBS_LOCK:

                    SIM_JOBS[job_id]["progress"] = min(
                        100,
                        val
                    )

            res = live_simulator.build(
                body,
                progress_callback=progress_cb
            )

            with SIM_JOBS_LOCK:

                SIM_JOBS[job_id]["status"] = "completed"

                SIM_JOBS[job_id]["progress"] = 100

                SIM_JOBS[job_id]["result"] = res

        except Exception as e:

            error_trace = traceback.format_exc()

            print(
                f"[LIVE SIMULATOR ERROR]\n"
                f"{error_trace}"
            )

            with SIM_JOBS_LOCK:

                SIM_JOBS[job_id]["status"] = "failed"

                SIM_JOBS[job_id]["error"] = str(e)

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()

    return jsonify({

        "success": True,

        "message": (
            "Live simulator job dimulai."
        ),

        "job_id": job_id

    }), 200


# ============================================================
# LIVE SIMULATOR STATUS
# ============================================================

@app.route(
    "/api/simulate/status/<job_id>",
    methods=["GET"]
)
def simulate_status(job_id):

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


# ============================================================
# LIVE SIMULATOR DATA
# ============================================================

@app.route(
    "/api/simulate/data/<job_id>",
    methods=["GET"]
)
def simulate_data(job_id):

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
            "message": (
                f"Simulasi belum selesai. "
                f"Status: {j['status']}"
            )
        }), 400

    return jsonify({

        "success": True,

        "job_id": job_id,

        "data": j.get("result")

    }), 200

# ============================================================
# ROUTES - REPORT
# ============================================================

@app.route(
    "/api/report/<job_id>",
    methods=["GET"]
)
def get_report(job_id):

    with JOBS_LOCK:

        j = JOBS.get(job_id)

    if not j or not j.get("result"):

        return jsonify({

            "success": False,

            "message": (
                "Report tidak ditemukan. "
                "Pastikan backtest sudah selesai."
            )

        }), 404

    try:

        html_content = (
            ReportGenerator.generate_html_report(
                job_id,
                j["result"],
                j.get("params", {})
            )
        )

        return Response(
            html_content,
            mimetype="text/html"
        )

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error generating report: {str(e)}"
            )

        }), 500


# ============================================================
# DOWNLOAD REPORT
# ============================================================

@app.route(
    "/api/report/<job_id>/download",
    methods=["GET"]
)
def download_report(job_id):

    with JOBS_LOCK:

        j = JOBS.get(job_id)

    if not j or not j.get("result"):

        return jsonify({

            "success": False,

            "message": "Report tidak ditemukan."

        }), 404

    try:

        html_content = (
            ReportGenerator.generate_html_report(
                job_id,
                j["result"],
                j.get("params", {})
            )
        )

        report_filename = (
            f"report_{job_id[:8]}.html"
        )

        report_path = os.path.join(
            UPLOAD_DIR,
            report_filename
        )

        with open(
            report_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html_content)

        return send_from_directory(
            UPLOAD_DIR,
            report_filename,
            as_attachment=True
        )

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error downloading report: {str(e)}"
            )

        }), 500


# ============================================================
# HISTORY
# ============================================================

@app.route(
    "/api/history",
    methods=["GET"]
)
def get_history():

    limit = request.args.get(
        "limit",
        50,
        type=int
    )

    try:

        history = db.get_history(
            limit=limit
        )

        return jsonify({

            "success": True,

            "history": history,

            "count": len(history),

            "limit": limit

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error mengambil histori: {str(e)}"
            )

        }), 500


# ============================================================
# HISTORY DETAIL
# ============================================================

@app.route(
    "/api/history/<job_id>",
    methods=["GET"]
)
def get_history_detail(job_id):

    try:

        with JOBS_LOCK:

            j = JOBS.get(job_id)

        if j and j.get("result"):

            return jsonify({

                "success": True,

                "data": j["result"],

                "params": j.get("params"),

                "from_cache": True

            }), 200

        history = db.get_history(
            limit=1000
        )

        for record in history:

            if record.get("job_id") == job_id:

                return jsonify({

                    "success": True,

                    "data": record,

                    "from_cache": False

                }), 200

        return jsonify({

            "success": False,

            "message": (
                "Job ID tidak ditemukan di database."
            )

        }), 404

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error mengambil detail: {str(e)}"
            )

        }), 500


# ============================================================
# CLEAR HISTORY
# ============================================================

@app.route(
    "/api/history/clear",
    methods=["POST"]
)
def clear_history():

    try:

        with JOBS_LOCK:

            JOBS.clear()

        return jsonify({

            "success": True,

            "message": (
                "Histori backtest berhasil dihapus."
            )

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error menghapus histori: {str(e)}"
            )

        }), 500


# ============================================================
# PORTFOLIO
# ============================================================

@app.route(
    "/api/portfolio",
    methods=["GET"]
)
def get_portfolio():

    try:

        history = db.get_history(
            limit=1000
        )

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

        total_runs = len(history)

        total_profit = sum(
            r.get("net_profit", 0)
            for r in history
        )

        avg_profit = (
            total_profit / total_runs
            if total_runs > 0
            else 0
        )

        winning_runs = [

            r for r in history

            if r.get("net_profit", 0) > 0
        ]

        win_rate = (

            len(winning_runs)
            / total_runs
            * 100

            if total_runs > 0
            else 0
        )

        best_ea = max(
            history,
            key=lambda x: x.get(
                "net_profit",
                0
            )
        )

        worst_ea = min(
            history,
            key=lambda x: x.get(
                "net_profit",
                0
            )
        )

        return jsonify({

            "success": True,

            "portfolio": {

                "total_runs": total_runs,

                "total_profit": round(
                    total_profit,
                    2
                ),

                "avg_profit": round(
                    avg_profit,
                    2
                ),

                "win_rate": round(
                    win_rate,
                    2
                ),

                "best_ea": {

                    "name": best_ea.get(
                        "ea_name"
                    ),

                    "profit": best_ea.get(
                        "net_profit"
                    )

                },

                "worst_ea": {

                    "name": worst_ea.get(
                        "ea_name"
                    ),

                    "profit": worst_ea.get(
                        "net_profit"
                    )

                }

            }

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": (
                f"Error menghitung portfolio: {str(e)}"
            )

        }), 500


# ============================================================
# DATA FILES
# ============================================================

@app.route('/api/data-files', methods=['GET'])
def get_data_files():
    """Mengambil daftar file CSV dari folder data/"""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        file_list = []
        
        for f in csv_files:
            fname = os.path.basename(f)
            # Ekstrak info simbol & timeframe jika sesuai format
            file_list.append({
                "filename": fname,
                "path": f
            })
            
        return jsonify({
            "success": True,
            "files": [f["filename"] for f in file_list],
            "details": file_list
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({

        "success": False,

        "message": (
            "Endpoint tidak ditemukan."
        )

    }), 404


@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "success": False,

        "message": (
            "Error internal server."
        )

    }), 500


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({

        "success": False,

        "message": (
            "Method tidak diizinkan."
        )

    }), 405


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "PINTARIN LABORATORIUM EA - BACKEND SERVER"
    )

    print("=" * 70)

    print(
        f"Port: {APP_PORT}"
    )

    print(
        f"Data Directory: {TICK_DATA_DIR}"
    )

    print(
        f"Upload Directory: {UPLOAD_DIR}"
    )

    print(
        f"Templates Directory: {TEMPLATES_DIR}"
    )

    print(
        f"Parquet Files Found: "
        f"{get_parquet_files_count()}"
    )

    print(
        f"AI Explainer: "
        f"{'READY' if AI_EXPLAINER_AVAILABLE else 'ERROR'}"
    )

    print(
        f"Live Simulator: "
        f"{'READY' if LIVE_SIMULATOR_AVAILABLE else 'ERROR'}"
    )

    print("=" * 70)

    print(
        "Starting Flask server..."
    )

    print("=" * 70)

    app.run(

        host="0.0.0.0",

        port=APP_PORT,

        debug=False,

        threaded=True
    )
