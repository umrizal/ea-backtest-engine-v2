# ============================================================
# patch_stage3_app.py
# Inject Stage 3 routes ke app.py
# ============================================================

import os
import sys

APP_FILE = "app.py"
MARKER = "# === STAGE3 ROUTES (auto-injected) ==="


def patch():
    if not os.path.exists(APP_FILE):
        print(f"[ERROR] {APP_FILE} tidak ditemukan.")
        sys.exit(1)

    with open(APP_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if MARKER in content:
        print("[OK] Stage 3 sudah terpasang.")
        return

    import_block = (
        "\n# Stage 3\n"
        "try:\n"
        "    from stage3_routes import register_stage3_routes\n"
        "    STAGE3_AVAILABLE = True\n"
        "except ImportError:\n"
        "    STAGE3_AVAILABLE = False\n"
        "    register_stage3_routes = None\n"
    )

    if "STAGE2_AVAILABLE" in content:
        content = content.replace(
            "STAGE2_AVAILABLE = False\n    register_stage2_routes = None",
            "STAGE2_AVAILABLE = False\n    register_stage2_routes = None" + import_block,
            1,
        )
    elif "from report_generator import ReportGenerator" in content:
        content = content.replace(
            "from report_generator import ReportGenerator",
            "from report_generator import ReportGenerator" + import_block,
            1,
        )
    else:
        content = content.replace("CORS(app)", "CORS(app)" + import_block, 1)

    register_block = f"""
{MARKER}
if STAGE3_AVAILABLE and register_stage3_routes is not None:
    try:
        _ss = None
        try:
            from sheet_sync import SheetSyncManager
            _ss = SheetSyncManager()
        except Exception:
            pass
        register_stage3_routes(
            app,
            bt_engine=bt_engine,
            sheet_sync=_ss,
        )
        print("[INIT] Stage 3 routes registered.")
    except Exception as _s3_err:
        print(f"[WARNING] Stage 3 routes gagal: {{_s3_err}}")
# === END STAGE3 ===

"""

    if "# === END STAGE2 ===" in content:
        content = content.replace(
            "# === END STAGE2 ===",
            "# === END STAGE2 ===\n" + register_block,
            1,
        )
    elif 'if __name__ == "__main__":' in content:
        content = content.replace(
            'if __name__ == "__main__":',
            register_block + 'if __name__ == "__main__":',
            1,
        )
    else:
        content += "\n" + register_block

    with open(APP_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("[OK] app.py di-patch untuk Stage 3.")
    print("     File yang dibutuhkan di root:")
    print("       stage3_routes.py, walkforward.py, condition_builder.py,")
    print("       portfolio_compare.py, report_export.py")
    print("       stage3_frontend.js → static/")


if __name__ == "__main__":
    patch()
