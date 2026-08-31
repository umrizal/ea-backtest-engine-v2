# ============================================================
# patch_stage2_app.py
# Pintarin Laboratorium EA – Stage 2
#
# Cara pakai (sekali jalan di root project):
#   python patch_stage2_app.py
#
# Script ini menambahkan import + register_stage2_routes
# ke app.py tanpa merusak kode yang sudah ada.
# ============================================================

import os
import sys

APP_FILE = "app.py"
MARKER = "# === STAGE2 ROUTES (auto-injected) ==="


def patch():
    if not os.path.exists(APP_FILE):
        print(f"[ERROR] {APP_FILE} tidak ditemukan di direktori ini.")
        sys.exit(1)

    with open(APP_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if MARKER in content:
        print("[OK] Stage 2 routes sudah terpasang sebelumnya.")
        return

    # 1. Tambah import di bagian atas (setelah import lain)
    import_line = (
        "\n# Stage 2\n"
        "try:\n"
        "    from stage2_routes import register_stage2_routes\n"
        "    STAGE2_AVAILABLE = True\n"
        "except ImportError:\n"
        "    STAGE2_AVAILABLE = False\n"
        "    register_stage2_routes = None\n"
    )

    # Cari posisi setelah baris "from report_generator import ..." atau sejenis
    anchor = "from report_generator import ReportGenerator"
    if anchor in content:
        content = content.replace(anchor, anchor + import_line, 1)
    else:
        # fallback: setelah CORS
        content = content.replace(
            "CORS(app)",
            "CORS(app)" + import_line,
            1,
        )

    # 2. Register routes sebelum if __name__
    register_block = f"""
{MARKER}
if STAGE2_AVAILABLE and register_stage2_routes is not None:
    try:
        register_stage2_routes(
            app,
            ai_explainer=ai_explainer if AI_EXPLAINER_AVAILABLE else None,
            bt_engine=bt_engine,
        )
        print("[INIT] Stage 2 routes registered.")
    except Exception as _s2_err:
        print(f"[WARNING] Stage 2 routes gagal: {{_s2_err}}")
# === END STAGE2 ===

"""

    if 'if __name__ == "__main__":' in content:
        content = content.replace(
            'if __name__ == "__main__":',
            register_block + 'if __name__ == "__main__":',
            1,
        )
    elif "app.run(" in content:
        # fallback
        idx = content.rfind("app.run(")
        content = content[:idx] + register_block + content[idx:]
    else:
        content += "\n" + register_block

    with open(APP_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("[OK] app.py berhasil di-patch untuk Stage 2.")
    print("     Pastikan file berikut ada di root:")
    print("       - stage2_routes.py")
    print("       - ai_explainer.py (Stage 1)")
    print("       - ea_parser_ai.py (Stage 1)")
    print("       - stage2_frontend.js  → copy ke static/ atau templates/")


if __name__ == "__main__":
    patch()
