# ai_explainer.py

import os
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.getenv(
    "FLAZ_API_KEY",
    "sk-P9rVt9W7B7JosCPzfIrknQ"
)

BASE_URL = os.getenv(
    "FLAZ_BASE_URL",
    "https://ai.flaz.id/v1"
)

MODEL = os.getenv(
    "FLAZ_MODEL",
    "gpt-5.4-nano"
)


# ============================================================
# OPENAI CLIENT
# ============================================================

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
Anda adalah AI expert dalam membaca dan menjelaskan Expert Advisor
(EA) MetaTrader 5 menggunakan bahasa pemrograman MQL5.

Tugas Anda adalah menganalisis SOURCE CODE MQL5 yang diberikan.
Jangan melakukan parsing AST atau mengandalkan struktur AST.
Analisis langsung teks source code yang diberikan.

Jelaskan EA secara teknis tetapi mudah dipahami oleh trader maupun
programmer.

Struktur penjelasan yang harus digunakan:

1. RINGKASAN EA
   - Jelaskan fungsi utama EA.
   - Jelaskan jenis trading yang kemungkinan digunakan.
   - Jelaskan timeframe/symbol jika dapat diketahui dari kode.

2. PARAMETER INPUT
   Jelaskan input-input penting, termasuk jika tersedia:
   - Lot
   - Take Profit
   - Stop Loss
   - Trailing Stop
   - Magic Number
   - Spread
   - Slippage/deviation
   - Maximum position/layer
   - Trading time
   - Parameter indikator
   - Parameter risk management
   - Parameter lainnya yang relevan

3. STRATEGI UTAMA
   Identifikasi strategi berdasarkan source code.
   Contoh:
   - Moving Average crossover
   - RSI
   - MACD
   - Bollinger Bands
   - Fractal
   - ADX / DI
   - Price action
   - Grid
   - Martingale
   - Hedging
   - Breakout
   - Trend following
   - Scalping
   Jika menggunakan kombinasi beberapa indikator, jelaskan hubungannya.

4. ENTRY RULE
   Jelaskan secara detail:
   - Kapan BUY dibuka.
   - Kapan SELL dibuka.
   - Filter yang harus terpenuhi.
   - Kondisi indikator jika ada.

5. EXIT RULE
   Jelaskan:
   - Take Profit.
   - Stop Loss.
   - Trailing Stop.
   - Close berdasarkan sinyal berlawanan.
   - Close berdasarkan basket profit/loss.
   - Close berdasarkan waktu.
   - Kondisi exit lainnya.

6. MANAJEMEN LOT
   Identifikasi apakah EA menggunakan:
   - Fixed lot
   - Dynamic lot
   - Risk percentage
   - Martingale
   - Lot multiplier
   - Grid/layering
   - Recovery
   Jelaskan mekanismenya dan berikan contoh sederhana jika memungkinkan.

7. MANAJEMEN RISIKO
   Jelaskan bagaimana EA mengontrol risiko.
   Jika tidak ada risk management yang memadai, katakan dengan jelas.

8. ALUR EKSEKUSI EA
   Jelaskan secara sederhana apa yang terjadi ketika:
   - EA mulai
   - Tick baru masuk
   - Sinyal muncul
   - Position dibuka
   - Position dikelola
   - Position ditutup

9. RISIKO DAN EDGE CASE
   Cari potensi masalah seperti:
   - Overtrading
   - False signal
   - Spread besar
   - Slippage
   - Requote/execution failure
   - Market sideways
   - Multiple position
   - Grid exposure
   - Martingale risk
   - Lot terlalu besar
   - Stop Loss tidak efektif
   - Broker limitations
   - Trading pada news
   - Trading session
   - Restart terminal
   - Duplicate order
   - Indicator buffer/copy error
   - Masalah pada VPS atau koneksi

10. KESIMPULAN
   Berikan kesimpulan singkat mengenai:
   - Cara kerja EA.
   - Kelebihan.
   - Kelemahan.
   - Risiko utama.

Jangan mengarang fitur yang tidak terdapat dalam source code.
Jika suatu fitur tidak ditemukan, tuliskan "Tidak ditemukan dalam kode".

Jika ada bagian kode yang ambigu, jelaskan bahwa kesimpulan tersebut
merupakan indikasi berdasarkan kode yang tersedia.

Gunakan Bahasa Indonesia.
"""


# ============================================================
# PROMPT BUILDER
# ============================================================

def build_prompt(mql5_code: str) -> str:
    """
    Membuat prompt final yang dikirim ke AI.
    """
    return f"""
{SYSTEM_PROMPT}

============================================================
SOURCE CODE EA MT5 / MQL5
============================================================

```mql5
{mql5_code}
```

============================================================
INSTRUKSI:
Jelaskan EA di atas sesuai struktur yang telah ditentukan.
Gunakan Bahasa Indonesia yang jelas dan teknis.
"""


# ============================================================
# EXPLAIN EA FUNCTION
# ============================================================

def explain_ea(mql5_code: str) -> str:
    """
    Mengirim kode MQL5 ke AI dan mengembalikan penjelasan.
    
    Args:
        mql5_code (str): Source code EA dalam format MQL5
        
    Returns:
        str: Penjelasan EA dalam format terstruktur
    """
    if not mql5_code or not mql5_code.strip():
        return "❌ Kode MQL5 kosong. Harap paste atau upload file EA terlebih dahulu."
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(mql5_code)}
            ],
            temperature=0.3,
            max_tokens=2500,
            timeout=60
        )
        
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        else:
            return "⚠️ AI tidak memberikan respon. Silakan coba lagi."
            
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return f"❌ Error autentikasi API. Periksa FLAZ_API_KEY Anda."
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return f"⚠️ Error koneksi ke AI server. Periksa koneksi internet Anda."
        else:
            return f"❌ Error menganalisis EA: {error_msg}"


# ============================================================
# CLASS-BASED INTERFACE (Optional)
# ============================================================

class AIExplainer:
    """
    Class-based interface untuk AI Explainer.
    Digunakan oleh app.py untuk konsistensi dengan engine lainnya.
    """
    
    @staticmethod
    def explain_ea(mql5_code: str) -> str:
        """
        Static method untuk menjelaskan EA MQL5.
        
        Args:
            mql5_code (str): Source code EA dalam format MQL5
            
        Returns:
            str: Penjelasan EA dalam format terstruktur
        """
        return explain_ea(mql5_code)
    
    @staticmethod
    def validate_code(mql5_code: str) -> dict:
        """
        Validasi apakah kode yang diberikan adalah kode MQL5 yang valid.
        
        Args:
            mql5_code (str): Source code untuk divalidasi
            
        Returns:
            dict: Hasil validasi dengan keys: is_valid, issues, detected_features
        """
        result = {
            "is_valid": False,
            "issues": [],
            "detected_features": []
        }
        
        if not mql5_code or not mql5_code.strip():
            result["issues"].append("Kode kosong")
            return result
        
        # Check for basic MQL5 structure
        has_on_tick = "void OnTick()" in mql5_code or "void OnTick()" in mql5_code
        has_on_init = "int OnInit()" in mql5_code or "bool OnInit()" in mql5_code
        has_input = "input " in mql5_code
        
        if has_on_tick:
            result["detected_features"].append("OnTick handler")
        if has_on_init:
            result["detected_features"].append("OnInit handler")
        if has_input:
            result["detected_features"].append("Input parameters")
        
        # Check for common MQL5 functions
        mql5_patterns = [
            "OrderSend", "PositionSelect", "SymbolInfo", "iMA", "iRSI", 
            "iMACD", "iBands", "iATR", "CopyClose", "CopyOpen", "CopyHigh", "CopyLow"
        ]
        
        for pattern in mql5_patterns:
            if pattern in mql5_code:
                result["detected_features"].append(f"Uses {pattern}")
        
        # Determine validity
        if has_on_tick or (has_on_init and len(result["detected_features"]) >= 2):
            result["is_valid"] = True
        else:
            result["issues"].append("Struktur EA MQL5 tidak terdeteksi (missing OnTick/OnInit)")
        
        return result


# ============================================================
# TEST FUNCTION (for development)
# ============================================================

if __name__ == "__main__":
    # Test code
    test_code = """
input double TakeProfit = 50.0;
input double StopLoss = 30.0;
input int FastMA = 10;
input int SlowMA = 30;

int OnInit() {
    return INIT_SUCCEEDED;
}

void OnTick() {
    double ma1 = iMA(_Symbol, _Period, FastMA, 0, MODE_SMA, PRICE_CLOSE);
    double ma2 = iMA(_Symbol, _Period, SlowMA, 0, MODE_SMA, PRICE_CLOSE);
    
    if(ma1 > ma2 && PositionsTotal() == 0) {
        OrderSend(...); // BUY
    }
}
"""
    
    print("Testing AI Explainer...")
    print("=" * 60)
    explanation = explain_ea(test_code)
    print(explanation)
