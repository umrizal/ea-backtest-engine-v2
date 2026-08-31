# ============================================================
# ai_explainer.py
# Pintarin Laboratorium EA - AI Explainer Engine (Stage 1)
#
# Fitur:
#   - explain_ea()          → teks penjelasan (kompatibel lama)
#   - analyze_structured()  → JSON structured trading_logic
#                             yang langsung dipakai BacktestEngine
# ============================================================

import os
import re
import json
from typing import Any, Dict, Optional

from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.getenv("FLAZ_API_KEY", "sk-rZLDmCndTU3LC8mO2TQ4Ow")
BASE_URL = os.getenv("FLAZ_BASE_URL", "https://ai.flaz.id/v1")
MODEL = os.getenv("FLAZ_MODEL", "gpt-5.4-nano")

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    timeout=120.0,
    max_retries=2,
)

# ============================================================
# SYSTEM PROMPT – TEXT (kompatibel dengan UI lama)
# ============================================================

SYSTEM_PROMPT_TEXT = """
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
# SYSTEM PROMPT – STRUCTURED JSON (untuk engine)
# ============================================================

SYSTEM_PROMPT_STRUCTURED = """
Anda adalah AI Expert MQL5 yang bertugas mengekstrak logika trading dari kode Expert Advisor menjadi JSON terstruktur yang bisa dieksekusi oleh engine backtest Python.

ATURAN KERAS:
1. Output HANYA berupa JSON valid. Tidak boleh ada teks, markdown, atau penjelasan di luar JSON.
2. Jangan berhalusinasi. Jika suatu parameter tidak ditemukan di kode, gunakan nilai default yang masuk akal atau null.
3. Semua angka harus bertipe number (bukan string).
4. strategy_type harus salah satu dari:
   "ma_crossover", "rsi", "macd", "bollinger", "stochastic",
   "trend_following", "grid", "martingale", "breakout",
   "price_action", "scalping", "alligator", "fractal", "other"

STRUKTUR JSON YANG WAJIB DIIKUTI:

{
  "strategy_type": "ma_crossover",
  "summary": {
    "name": "Nama EA jika ada",
    "description": "1 kalimat ringkas cara kerja",
    "timeframe": "H1 atau null",
    "pair": "XAUUSD atau null"
  },
  "indicators": [
    {
      "name": "MA",
      "type": "SMA",
      "period": 10,
      "shift": 0,
      "price": "close",
      "role": "fast"
    },
    {
      "name": "MA",
      "type": "SMA",
      "period": 30,
      "shift": 0,
      "price": "close",
      "role": "slow"
    }
  ],
  "entry_rules": {
    "buy": ["fast MA crosses above slow MA"],
    "sell": ["fast MA crosses below slow MA"]
  },
  "exit_rules": {
    "tp": 50.0,
    "sl": 30.0,
    "tp_unit": "pips",
    "sl_unit": "pips",
    "trailing": 0.0,
    "breakeven": 0.0,
    "opposite_signal": false,
    "time_exit": null,
    "basket_profit": null,
    "basket_loss": null
  },
  "lot_management": {
    "type": "fixed",
    "base_lot": 0.1,
    "multiplier": 1.0,
    "martingale": false,
    "max_lot": 100.0
  },
  "risk_management": {
    "max_positions": 1,
    "use_hedging": false,
    "max_spread": null,
    "max_daily_loss": null,
    "max_drawdown": null
  },
  "time_filters": {
    "enabled": false,
    "start_hour": 0,
    "end_hour": 24
  },
  "execution": {
    "entry_on_next_bar": false,
    "slippage_points": 0,
    "commission_per_lot": 0
  },
  "bugs": [],
  "risks": []
}

Catatan penting:
- tp/sl bisa dalam "pips" atau "points" atau "currency".
- Jika EA menggunakan Martingale/Grid, set lot_management.martingale = true dan risk_management.max_positions > 1.
- role indikator: "fast", "slow", "signal", "filter", "main".
"""

# ============================================================
# PROMPT BUILDERS
# ============================================================

def _build_text_prompt(mql5_code: str, file_name: str = "EA_Model") -> str:
    header = "=" * 60
    truncated = mql5_code[:15000] if len(mql5_code) > 15000 else mql5_code
    return (
        f"{header}\n"
        f"NAMA FILE / EA: {file_name}\n"
        f"SOURCE CODE MQL5:\n```mql5\n{truncated}\n```\n"
        f"{header}\n"
        "INSTRUKSI:\nBedah kode MQL5 di atas. Cantumkan nama EA yang terdeteksi di judul Ringkasan EA."
    )


def _build_structured_prompt(mql5_code: str, file_name: str = "EA_Model") -> str:
    header = "=" * 60
    truncated = mql5_code[:18000] if len(mql5_code) > 18000 else mql5_code
    return (
        f"{header}\n"
        f"NAMA FILE / EA: {file_name}\n"
        f"SOURCE CODE MQL5:\n```mql5\n{truncated}\n```\n"
        f"{header}\n"
        "INSTRUKSI:\n"
        "Ekstrak logika trading dari kode di atas menjadi JSON sesuai skema yang ditentukan. "
        "Output HANYA JSON valid, tanpa teks lain."
    )


# ============================================================
# HELPER: Extract JSON from AI response
# ============================================================

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Coba ambil objek JSON dari response AI (bisa ada markdown wrapper)."""
    if not text:
        return None

    text = text.strip()

    # Langsung parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Cari blok ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Cari kurung kurawal paling luar
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ============================================================
# CORE FUNCTIONS
# ============================================================

def explain_ea(mql5_code: str, file_name: str = "Expert Advisor") -> str:
    """Menghasilkan penjelasan teks (kompatibel UI lama)."""
    if not mql5_code or not mql5_code.strip():
        return "❌ Kode MQL5 kosong. Harap paste atau upload file EA terlebih dahulu."

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEXT},
                {"role": "user", "content": _build_text_prompt(mql5_code, file_name)},
            ],
            temperature=0.2,
            max_tokens=1400,
        )

        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        return "❌ AI tidak memberikan respon. Silakan coba lagi."

    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return "❌ Error autentikasi API. Periksa FLAZ_API_KEY Anda."
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return "❌ Error koneksi/timeout ke server AI Flaz."
        return f"❌ Error menganalisis EA: {error_msg}"


def _default_trading_logic() -> Dict[str, Any]:
    """Default structure yang sama dengan BacktestEngine._default_logic()."""
    return {
        "strategy_type": "ma_crossover",
        "indicators": [
            {"name": "MA", "type": "SMA", "period": 10, "role": "fast"},
            {"name": "MA", "type": "SMA", "period": 30, "role": "slow"},
        ],
        "entry_rules": {
            "buy": ["fast MA crosses above slow MA"],
            "sell": ["fast MA crosses below slow MA"],
        },
        "exit_rules": {
            "tp": 50.0,
            "sl": 30.0,
            "tp_unit": "pips",
            "sl_unit": "pips",
            "trailing": 0.0,
            "breakeven": 0.0,
            "opposite_signal": False,
            "time_exit": None,
            "basket_profit": None,
            "basket_loss": None,
        },
        "lot_management": {
            "type": "fixed",
            "base_lot": 0.1,
            "multiplier": 1.0,
            "martingale": False,
            "max_lot": 100.0,
        },
        "risk_management": {
            "max_positions": 1,
            "use_hedging": False,
            "max_spread": None,
            "max_daily_loss": None,
            "max_drawdown": None,
        },
        "time_filters": {
            "enabled": False,
            "start_hour": 0,
            "end_hour": 24,
        },
        "execution": {
            "entry_on_next_bar": False,
            "slippage_points": 0,
            "commission_per_lot": 0,
        },
        "bugs": [],
        "risks": [],
        "explanation_raw": "",
        "summary": {
            "name": None,
            "description": None,
            "timeframe": None,
            "pair": None,
        },
    }


def analyze_structured(mql5_code: str, file_name: str = "Expert Advisor") -> Dict[str, Any]:
    """
    Menghasilkan trading_logic structured yang langsung
    bisa dipakai BacktestEngine._analyze_mql5_code().
    """
    default = _default_trading_logic()

    if not mql5_code or not mql5_code.strip():
        return default

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_STRUCTURED},
                {"role": "user", "content": _build_structured_prompt(mql5_code, file_name)},
            ],
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"} if "gpt" in MODEL.lower() else None,
        )

        raw = ""
        if response.choices and len(response.choices) > 0:
            raw = response.choices[0].message.content.strip()

        parsed = _extract_json(raw)
        if not parsed or not isinstance(parsed, dict):
            # Fallback ke parsing teks + regex
            text_expl = explain_ea(mql5_code, file_name)
            return _fallback_from_text(text_expl, mql5_code, default)

        # Merge dengan default agar field wajib selalu ada
        logic = _merge_with_default(parsed, default)
        logic["explanation_raw"] = raw
        return logic

    except Exception as e:
        print(f"[AI] analyze_structured failed: {e}")
        text_expl = explain_ea(mql5_code, file_name)
        return _fallback_from_text(text_expl, mql5_code, default)


def _merge_with_default(parsed: Dict, default: Dict) -> Dict:
    """Merge hasil AI dengan default, jaga struktur."""
    result = default.copy()

    # Top-level keys
    for key in [
        "strategy_type",
        "indicators",
        "entry_rules",
        "exit_rules",
        "lot_management",
        "risk_management",
        "time_filters",
        "execution",
        "bugs",
        "risks",
    ]:
        if key in parsed and parsed[key] is not None:
            if isinstance(parsed[key], dict) and isinstance(result.get(key), dict):
                result[key] = {**result[key], **parsed[key]}
            else:
                result[key] = parsed[key]

    # summary (opsional)
    if "summary" in parsed and isinstance(parsed["summary"], dict):
        result["summary"] = parsed["summary"]

    # Normalisasi strategy_type
    valid_types = {
        "ma_crossover", "rsi", "macd", "bollinger", "stochastic",
        "trend_following", "grid", "martingale", "breakout",
        "price_action", "scalping", "alligator", "fractal", "other",
    }
    st = str(result.get("strategy_type", "ma_crossover")).lower().strip()
    if st not in valid_types:
        # mapping umum
        mapping = {
            "moving average": "ma_crossover",
            "ma": "ma_crossover",
            "ema crossover": "ma_crossover",
            "trend": "trend_following",
            "grid martingale": "martingale",
        }
        st = mapping.get(st, "other")
    result["strategy_type"] = st

    # Pastikan indicators list of dict
    inds = result.get("indicators", [])
    if inds and isinstance(inds[0], str):
        result["indicators"] = [{"name": n, "period": 14} for n in inds]

    return result


def _fallback_from_text(explanation: str, mql5_code: str, default: Dict) -> Dict:
    """Fallback jika structured gagal: parse dari teks + regex kode."""
    logic = default.copy()
    logic["explanation_raw"] = explanation or ""

    text = ((explanation or "") + "\n" + (mql5_code or "")).lower()

    strategy_patterns = [
        (["moving average", "ma crossover", "ema crossover", "iMA"], "ma_crossover"),
        (["rsi", "irsi"], "rsi"),
        (["macd", "imacd"], "macd"),
        (["bollinger", "ibands"], "bollinger"),
        (["stochastic", "istochastic"], "stochastic"),
        (["adx", "directional index"], "trend_following"),
        (["grid"], "grid"),
        (["martingale"], "martingale"),
        (["breakout"], "breakout"),
        (["price action"], "price_action"),
        (["scalping"], "scalping"),
        (["alligator"], "alligator"),
        (["fractal"], "fractal"),
    ]

    for keywords, strategy in strategy_patterns:
        if any(k in text for k in keywords):
            logic["strategy_type"] = strategy
            break

    # Deteksi martingale / grid dari kode
    if re.search(r"martingale|lot\s*\*\s*|multiplier", mql5_code or "", re.I):
        logic["lot_management"]["martingale"] = True
        logic["lot_management"]["type"] = "martingale"
        logic["strategy_type"] = "martingale" if logic["strategy_type"] == "ma_crossover" else logic["strategy_type"]

    # Extract TP / SL dari input
    def _extract_num(names, default_val):
        for name in names:
            pat = rf"(?:input\s+)?(?:double|int|long)?\s*{re.escape(name)}\s*=\s*([-+]?\d*\.?\d+)"
            m = re.search(pat, mql5_code or "", re.I)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return default_val

    logic["exit_rules"]["tp"] = _extract_num(
        ["TakeProfit", "InpTakeProfit", "TP", "tp"], logic["exit_rules"]["tp"]
    )
    logic["exit_rules"]["sl"] = _extract_num(
        ["StopLoss", "InpStopLoss", "SL", "sl"], logic["exit_rules"]["sl"]
    )
    logic["exit_rules"]["trailing"] = _extract_num(
        ["TrailingStop", "InpTrailingStop", "Trailing"], 0.0
    )
    logic["lot_management"]["base_lot"] = _extract_num(
        ["Lot", "InpLot", "Lots", "LotSize"], 0.1
    )
    logic["lot_management"]["multiplier"] = _extract_num(
        ["Multiplier", "LotMultiplier", "MartingaleFactor"], 1.0
    )

    return logic


# ============================================================
# CLASS-BASED INTERFACE (kompatibel dengan app.py & engine)
# ============================================================

class AIExplainer:
    """Class-based interface untuk AI Explainer."""

    def __init__(self):
        pass

    def explain_ea(self, mql5_code: str, file_name: str = "Expert Advisor") -> str:
        return explain_ea(mql5_code, file_name)

    def analyze_structured(self, mql5_code: str, file_name: str = "Expert Advisor") -> Dict[str, Any]:
        return analyze_structured(mql5_code, file_name)

    def validate_code(self, mql5_code: str) -> dict:
        result = {
            "is_valid": False,
            "issues": [],
            "detected_features": [],
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
            result["issues"].append(
                "Struktur EA MQL5 tidak terdeteksi (missing OnTick/OnInit)"
            )

        return result
