# ai_explainer.py
# Pintarin Laboratorium EA - AI Explainer Engine

import os
from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.getenv("FLAZ_API_KEY", "sk-rZLDmCndTU3LC8mO2TQ4Ow")
BASE_URL = os.getenv("FLAZ_BASE_URL", "https://ai.flaz.id/v1")
MODEL = os.getenv("FLAZ_MODEL", "gpt-5.4-nano")

# Inisialisasi OpenAI Client dengan timeout 120 detik
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    timeout=120.0,
    max_retries=2
)

# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
Anda adalah AI Expert MQL5. Tugas Anda adalah membedah EA secara SINGKAT, PADAT, dan RAPI, serta MENEMUKAN BUG atau potensi masalah teknis pada kodenya.

ATURAN FORMATTING & GAYA BAHASA:
- Hindari paragraf panjang. Wajib gunakan poin-poin singkat (bullet points).
- Gunakan ikon visual emoji di setiap poin utama agar mudah dibaca sekilas.
- Minimalkan penggunaan tanda koma dan kalimat berbelit-belit. Langsung ke intinya.
- Jangan berhalusinasi. Jika fitur atau bug tidak ada di kode, tulis "❌ Tidak ditemukan".

STRUKTUR OUTPUT (WAJIB DITURUTI KONSISTEN):

📌 RINGKASAN EA
• 🎯 Tipe Strategi : [Scalping / Grid / Martingale / Trend Following / Breakout / dsb]
• ⏱️ Timeframe/Pair : [Detail jika ada / ❌ Tidak ditentukan]
• 📝 Cara Kerja    : [1 kalimat ringkas logika utamanya]

⚙️ PARAMETER UTAMA
• 💰 Lot Setup    : [Fixed Lot / Dynamic Lot / Martingale Multiplier]
• 🎯 TP / SL      : [Target Pips / Currency / Trailing Stop / ❌ Tidak ada]
• 🛡️ Risk Limit   : [Max Layer / Equity Protection / ❌ Tidak ada]
• 🎛️ Indikator    : [Daftar indikator teknikal yang dipakai]

📊 ATURAN ENTRY & EXIT
• 🟢 Sinyal BUY   : [Syarat singkat eksekusi beli]
• 🔴 Sinyal SELL  : [Syarat singkat eksekusi jual]
• 🚪 Exit Rule    : [Syarat TP/SL/Close Signal/Basket Close]

🐛 TEMUAN BUG & SARAN PERBAIKAN
• 🔴 Bug Logika/Sintaks : [Jelaskan lokasi/fungsi bug MQL5, atau ❌ Tidak ditemukan]
• ⚠️ Potensi Error Run  : [Masalah eksekusi, misal: Unhandled Return Value, Off-by-one loop, Slippage, Margin Call, atau Array Out of Range]
• 🛠️ Saran Perbaikan    : [1-2 langkah konkret perbaikan kodingan untuk memperbaiki bug tersebut]

⚠️ RISIKO UTAMA
• 💥 [Risiko 1, misal: Exposure Martingale/Grid tinggi saat trending]
• ⚠️ [Risiko 2, misal: Tanpa Hard Stop Loss / rawan margin call]
• 🔌 [Risiko 3, misal: Sensitif terhadap Spacing & Slippage]

💡 KESIMPULAN & REKOMENDASI
• 🚀 Kelebihan    : [1 poin keunggulan utama]
• 💣 Kelemahan    : [1 poin kelemahan terbesar]
• 🛡️ Saran Risk   : [1 saran praktis penggunaan]
"""

# ============================================================
# PROMPT BUILDER
# ============================================================

def build_prompt(mql5_code: str, file_name: str = "EA_Model") -> str:
    header = "=" * 60
    truncated_code = mql5_code[:15000] if len(mql5_code) > 15000 else mql5_code
    return f"{header}\nNAMA FILE / EA: {file_name}\nSOURCE CODE MQL5:\n```mql5\n{truncated_code}\n```\n{header}\nINSTRUKSI:\nBedah kode MQL5 di atas. Cantumkan nama EA yang terdeteksi di judul Ringkasan EA."

# ============================================================
# EXPLAIN EA FUNCTION
# ============================================================

def explain_ea(mql5_code: str) -> str:
    """Mengirim kode MQL5 ke AI dan mengembalikan penjelasan ringkas beserta bug report."""
    if not mql5_code or not mql5_code.strip():
        return "❌ Kode MQL5 kosong. Harap paste atau upload file EA terlebih dahulu."
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(mql5_code)}
            ],
            temperature=0.2,
            max_tokens=1200
        )
        
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        else:
            return "❌ AI tidak memberikan respon. Silakan coba lagi."
            
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return "❌ Error autentikasi API. Periksa FLAZ_API_KEY Anda."
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return "❌ Error koneksi/timeout ke server AI Flaz."
        else:
            return f"❌ Error menganalisis EA: {error_msg}"

# ============================================================
# CLASS-BASED INTERFACE
# ============================================================

class AIExplainer:
    """Class-based interface untuk AI Explainer."""
    
    @staticmethod
    def explain_ea(mql5_code: str) -> str:
        return explain_ea(mql5_code)
    
    @staticmethod
    def validate_code(mql5_code: str) -> dict:
        result = {
            "is_valid": False,
            "issues": [],
            "detected_features": []
        }
        
        if not mql5_code or not mql5_code.strip():
            result["issues"].append("Kode kosong")
            return result
        
        has_on_tick = "OnTick" in mql5_code
        has_on_init = "OnInit" in mql5_code
        
        if has_on_tick:
            result["detected_features"].append("OnTick handler")
        if has_on_init:
            result["detected_features"].append("OnInit handler")
            
        if has_on_tick or has_on_init:
            result["is_valid"] = True
        else:
            result["issues"].append("Struktur EA MQL5 tidak terdeteksi (missing OnTick/OnInit)")
        
        return result