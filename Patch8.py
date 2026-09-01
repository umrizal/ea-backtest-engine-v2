#!/usr/bin/env python3
"""
patch8.py - Fix "Terjadi kesalahan koneksi ke AI Explainer" regression
            introduced by the "Bedah EA -> Pilih Mode Backtest (A/B)" change.

ROOT CAUSE:
  Sebelumnya tombol "Bedah EA" memanggil /api/explain-ea langsung (stabil).
  Perubahan terakhir membuatnya memanggil /api/explain-and-parse untuk
  sekaligus mendapat teks penjelasan + parameter hasil parsing (untuk Opsi B).
  Kalau endpoint /api/explain-and-parse tidak tersedia / error di server
  (mis. route belum ke-register, atau ai_explainer tidak punya method
  analyze_structured), fetch()/res.json() di browser melempar exception,
  dan itu tertangkap oleh catch{} umum yang menampilkan pesan
  "Terjadi kesalahan koneksi ke AI Explainer." -- padahal AI Explainer-nya
  sendiri sebenarnya baik-baik saja.

FIX:
  templates/index.html -> explainEaLogic():
    1) Penjelasan teks EA sekarang SELALU memakai /api/explain-ea (endpoint
       lama yang terbukti stabil) sebagai sumber utama, terpisah dari proses
       parsing parameter.
    2) Parsing parameter untuk "Opsi B - Parameter Manual" sekarang best
       effort: dipanggil setelah penjelasan berhasil, dibungkus try/catch
       sendiri. Kalau gagal/tidak tersedia, tombol Opsi B otomatis
       dinonaktifkan (dengan tooltip penjelasan) -- TANPA mengganggu hasil
       "Bedah EA" atau memunculkan pesan error koneksi lagi.
    3) Tombol Opsi B diberi id="btnOptionBParam" supaya bisa
       di-enable/disable sesuai ketersediaan hasil parsing.

Usage:
    cd /path/to/ea-backtest-engine-v2
    python3 patch8.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def patch_index_html():
    filepath = os.path.join(BASE_DIR, "templates", "index.html")
    if not os.path.exists(filepath):
        print("[SKIP] templates/index.html not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = []

    # ------------------------------------------------------------
    # 1) Tambahkan id="btnOptionBParam" ke tombol Opsi B
    # ------------------------------------------------------------
    btn_old = (
        '<button class="btn blue" style="width:100%;" '
        'onclick="Stage2.revealParamPanel()">'
        '\u2699\ufe0f Tampilkan &amp; Setel Parameter</button>'
    )
    btn_new = (
        '<button class="btn blue" style="width:100%;" id="btnOptionBParam" '
        'onclick="Stage2.revealParamPanel()">'
        '\u2699\ufe0f Tampilkan &amp; Setel Parameter</button>'
    )
    if btn_old in content:
        content = content.replace(btn_old, btn_new)
        changes.append('Added id="btnOptionBParam" to Opsi B button')
    elif 'id="btnOptionBParam"' in content:
        print('[SKIP] Opsi B button already has id="btnOptionBParam"')
    else:
        print("[WARN] Opsi B button markup not found (may already differ) - skipping this part")

    # ------------------------------------------------------------
    # 2) Ganti isi explainEaLogic() supaya penjelasan & parsing terpisah
    # ------------------------------------------------------------
    fn_old = """  async function explainEaLogic() {
    const code = document.getElementById('mql5CodeInput').value;
    const card = document.getElementById('aiExplainerCard');
    const box = document.getElementById('aiExplainerContent');
    const eaName = document.getElementById('eaName').value;
    const choiceCard = document.getElementById('backtestChoiceCard');

    if (!code.trim()) {
      alert("Harap tempelkan kode MQL5 (.mq5) terlebih dahulu.");
      return;
    }

    card.style.display = 'block';
    if (choiceCard) choiceCard.style.display = 'none';
    box.innerText = "AI sedang membaca & membedah struktur MQL5 serta mencari bug...";

    try {
      // Satu panggilan: teks penjelasan + parsing parameter sekaligus,
      // supaya setelah "Bedah EA" langsung tersedia 2 pilihan backtest.
      const data = await Stage2.explainAndParse(code, eaName || "Expert Advisor");

      if (data.explanation) {
        box.innerText = data.explanation;
        extractAndSetEAName(code);
      } else {
        box.innerText = data.error || "Gagal menganalisis kode.";
      }

      if (data.success) {
        // Siapkan (isi) panel parameter Opsi B tanpa langsung menampilkannya.
        if (data.editable && Object.keys(data.editable).length) {
          Stage2.populateParamPanel(data);
        }
        // Tampilkan kartu pilihan: A. Default EA, B. Parameter Manual.
        if (choiceCard) choiceCard.style.display = 'block';
      }
    } catch (e) {
      box.innerText = "Terjadi kesalahan koneksi ke AI Explainer.";
    }
  }"""

    fn_new = """  async function explainEaLogic() {
    const code = document.getElementById('mql5CodeInput').value;
    const card = document.getElementById('aiExplainerCard');
    const box = document.getElementById('aiExplainerContent');
    const eaName = document.getElementById('eaName').value;
    const choiceCard = document.getElementById('backtestChoiceCard');
    const btnOptionB = document.getElementById('btnOptionBParam');

    if (!code.trim()) {
      alert("Harap tempelkan kode MQL5 (.mq5) terlebih dahulu.");
      return;
    }

    card.style.display = 'block';
    if (choiceCard) choiceCard.style.display = 'none';
    box.innerText = "AI sedang membaca & membedah struktur MQL5 serta mencari bug...";

    // 1) Penjelasan teks -- endpoint asli /api/explain-ea yang sudah terbukti
    //    stabil. Ini WAJIB berhasil supaya "Bedah EA" tetap bekerja seperti
    //    sebelumnya, apa pun status endpoint parsing di bawah.
    let explanationOk = false;
    try {
      const res = await fetch(`${API_BASE}/api/explain-ea`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, file_name: eaName || "Expert Advisor" })
      });
      const data = await res.json();

      if (data.explanation) {
        box.innerText = data.explanation;
        extractAndSetEAName(code);
        explanationOk = true;
      } else {
        box.innerText = data.error || "Gagal menganalisis kode.";
      }
    } catch (e) {
      console.error("explain-ea gagal:", e);
      box.innerText = "Terjadi kesalahan koneksi ke AI Explainer.";
      return;
    }

    if (!explanationOk) return;

    // 2) Parsing parameter untuk Opsi B -- best effort. Kalau endpoint ini
    //    error/tidak tersedia di server, JANGAN sampai mengganggu hasil
    //    Bedah EA di atas: cukup nonaktifkan tombol Opsi B.
    try {
      const parsed = await Stage2.explainAndParse(code, eaName || "Expert Advisor");
      if (parsed && parsed.success && parsed.editable && Object.keys(parsed.editable).length) {
        Stage2.populateParamPanel(parsed);
        if (btnOptionB) {
          btnOptionB.disabled = false;
          btnOptionB.title = "";
        }
      } else {
        if (btnOptionB) {
          btnOptionB.disabled = true;
          btnOptionB.title = "Parsing parameter tidak tersedia untuk EA ini.";
        }
      }
    } catch (e) {
      console.warn("Parsing parameter untuk Opsi B gagal (Opsi A tetap jalan):", e);
      if (btnOptionB) {
        btnOptionB.disabled = true;
        btnOptionB.title = "Parsing parameter gagal. Endpoint /api/explain-and-parse bermasalah di server.";
      }
    }

    if (choiceCard) choiceCard.style.display = 'block';
  }"""

    if fn_old in content:
        content = content.replace(fn_old, fn_new)
        changes.append("Decoupled explainEaLogic(): explanation now uses /api/explain-ea directly again; param parsing for Opsi B is best-effort")
    elif "explanationOk" in content:
        print("[SKIP] explainEaLogic() already patched")
    else:
        print("[ERROR] Could not find explainEaLogic() block to patch - file may have changed.")
        print("        Please check templates/index.html manually around 'async function explainEaLogic'.")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        for c in changes:
            print(f"  [OK] {c}")
        print(f"[DONE] Patched templates/index.html ({len(changes)} changes)")
    else:
        print("[SKIP] templates/index.html already patched or no match found")


def main():
    print("=" * 60)
    print("patch8.py - Fix 'Terjadi kesalahan koneksi ke AI Explainer'")
    print("=" * 60)
    print()

    print("[1/1] Patching templates/index.html (decouple Bedah EA explanation from param parsing)...")
    patch_index_html()
    print()

    print("=" * 60)
    print("DONE!")
    print()
    print("Summary of fix:")
    print("  - 'Bedah EA' text explanation now always calls /api/explain-ea")
    print("    directly again (the endpoint that was already proven stable).")
    print("  - Parameter parsing for 'Opsi B - Parameter Manual' now runs as a")
    print("    separate, best-effort step. If it fails, only the Opsi B button")
    print("    is disabled (with a tooltip) -- Bedah EA and Opsi A always work.")
    print("  - No more 'Terjadi kesalahan koneksi ke AI Explainer' just because")
    print("    the parsing endpoint had a problem.")
    print()
    print("NOTE: If Opsi B stays disabled after this fix, check server logs for")
    print("      /api/explain-and-parse - the route may not be registered")
    print("      (see stage2_routes.py registration in app.py) or")
    print("      ai_explainer might be missing the analyze_structured() method.")
    print("=" * 60)


if __name__ == "__main__":
    main()