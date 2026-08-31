import os
import re

def update_stage2_frontend():
    file_path = "stage2_frontend.js"
    if not os.path.exists(file_path):
        print(f"[SKIP] {file_path} tidak ditemukan.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Berikan offset/margin 2 candlestick di sumbu X chart simulator
    # Mengatur x-range margin pada LightWeight Charts / Chart.js / Highcharts
    if "setVisibleLogicalRange" in content:
        content = re.sub(
            r'setVisibleLogicalRange\(\{([^}]+)\}\)',
            r'setVisibleLogicalRange({ from: \1.from, to: \1.to + 2 })',
            content
        )
    elif "chart.timeScale().fitContent()" in content:
        content = content.replace(
            "chart.timeScale().fitContent();",
            "chart.timeScale().fitContent(); chart.timeScale().scrollToPosition(2, true);"
        )

    # 2. Sembunyikan Profit untuk transaksi yang masih Open (waktu tutup belum ada)
    # Ganti format render sel Profit di tabel trading
    old_profit_render = r'<td>\s*\$\{?\s*(row|trade)\.profit\b'
    new_profit_render = r'<td>${(\1.close_time || \1.closeTime) ? \1.profit.toFixed(2) : "-"}'
    content = re.sub(old_profit_render, new_profit_render, content)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[SUCCESS] Updated {file_path}")

def update_full_report_template():
    # Update template HTML Full Report agar sesuai format matriks MT4/MT5 dari screenshot
    report_html_path = os.path.join("templates", "report_template.html")
    if not os.path.exists(report_html_path):
        report_html_path = "templates/index.html" # Fallback ke index jika disatukan

    if not os.path.exists(report_html_path):
        print("[SKIP] Template laporan tidak ditemukan.")
        return

    report_matrix_component = """
    <!-- MT4/MT5 Standard Report Matrix -->
    <div class="report-matrix-container" style="background:#f4f4f4; padding:15px; font-family:Tahoma, Geneva, sans-serif; font-size:12px; border:1px solid #ccc;">
        <table style="width:100%; border-collapse:collapse; background:#fff;" border="1" cellpadding="4" cellspacing="0">
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">History Quality</td>
                <td>100%</td>
                <td style="font-weight:bold; background:#e6e6e6;">Bars</td>
                <td id="rep_bars">-</td>
                <td style="font-weight:bold; background:#e6e6e6;">Ticks</td>
                <td id="rep_ticks">-</td>
                <td style="font-weight:bold; background:#e6e6e6;">Symbols</td>
                <td>1</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Initial Deposit</td>
                <td id="rep_initial_deposit">10 000.00</td>
                <td colspan="6"></td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Total Net Profit</td>
                <td id="rep_net_profit">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Balance Drawdown Absolute</td>
                <td id="rep_bal_dd_abs">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Equity Drawdown Absolute</td>
                <td id="rep_eq_dd_abs">0.00</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Gross Profit</td>
                <td id="rep_gross_profit">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Balance Drawdown Maximal</td>
                <td id="rep_bal_dd_max">0.00 (0.00%)</td>
                <td style="font-weight:bold; background:#e6e6e6;">Equity Drawdown Maximal</td>
                <td id="rep_eq_dd_max">0.00 (0.00%)</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Gross Loss</td>
                <td id="rep_gross_loss">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Balance Drawdown Relative</td>
                <td id="rep_bal_dd_rel">0.00%</td>
                <td style="font-weight:bold; background:#e6e6e6;">Equity Drawdown Relative</td>
                <td id="rep_eq_dd_rel">0.00%</td>
            </tr>
            <tr style="border-top:2px solid #999;">
                <td style="font-weight:bold; background:#e6e6e6;">Profit Factor</td>
                <td id="rep_profit_factor">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Expected Payoff</td>
                <td id="rep_expected_payoff">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Margin Level</td>
                <td>9968.90%</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Recovery Factor</td>
                <td id="rep_recovery_factor">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Sharpe Ratio</td>
                <td id="rep_sharpe">0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">Z-Score</td>
                <td>0.00 (0.00%)</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">AHPR</td>
                <td id="rep_ahpr">1.0000</td>
                <td style="font-weight:bold; background:#e6e6e6;">LR Correlation</td>
                <td>0.00</td>
                <td style="font-weight:bold; background:#e6e6e6;">OnTester result</td>
                <td>0</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">GHPR</td>
                <td id="rep_ghpr">1.0000</td>
                <td style="font-weight:bold; background:#e6e6e6;">LR Standard Error</td>
                <td>0.00</td>
                <td colspan="2"></td>
            </tr>
            <tr style="border-top:2px solid #999;">
                <td style="font-weight:bold; background:#e6e6e6;">Total Trades</td>
                <td id="rep_total_trades">0</td>
                <td style="font-weight:bold; background:#e6e6e6;">Short Trades (won %)</td>
                <td id="rep_short_trades">0 (0.00%)</td>
                <td style="font-weight:bold; background:#e6e6e6;">Long Trades (won %)</td>
                <td id="rep_long_trades">0 (0.00%)</td>
            </tr>
            <tr>
                <td style="font-weight:bold; background:#e6e6e6;">Total Deals</td>
                <td id="rep_total_deals">0</td>
                <td style="font-weight:bold; background:#e6e6e6;">Profit Trades (% of total)</td>
                <td id="rep_profit_trades">0 (0.00%)</td>
                <td style="font-weight:bold; background:#e6e6e6;">Loss Trades (% of total)</td>
                <td id="rep_loss_trades">0 (0.00%)</td>
            </tr>
            <tr>
                <td></td>
                <td style="font-weight:bold; background:#e6e6e6;">Largest</td>
                <td>profit trade</td>
                <td id="rep_max_win">0.00</td>
                <td>loss trade</td>
                <td id="rep_max_loss">0.00</td>
            </tr>
            <tr>
                <td></td>
                <td style="font-weight:bold; background:#e6e6e6;">Average</td>
                <td>profit trade</td>
                <td id="rep_avg_win">0.00</td>
                <td>loss trade</td>
                <td id="rep_avg_loss">0.00</td>
            </tr>
            <tr>
                <td></td>
                <td style="font-weight:bold; background:#e6e6e6;">Maximum</td>
                <td>consecutive wins ($)</td>
                <td id="rep_max_consec_win">0 (0.00)</td>
                <td>consecutive losses ($)</td>
                <td id="rep_max_consec_loss">0 (0.00)</td>
            </tr>
            <tr>
                <td></td>
                <td style="font-weight:bold; background:#e6e6e6;">Maximal</td>
                <td>consecutive profit (count)</td>
                <td id="rep_consec_profit_cnt">0.00 (0)</td>
                <td>consecutive loss (count)</td>
                <td id="rep_consec_loss_cnt">0.00 (0)</td>
            </tr>
            <tr>
                <td></td>
                <td style="font-weight:bold; background:#e6e6e6;">Average</td>
                <td>consecutive wins</td>
                <td id="rep_avg_consec_win">0</td>
                <td>consecutive losses</td>
                <td id="rep_avg_consec_loss">0</td>
            </tr>
        </table>
    </div>
    """

    with open(report_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Menyisipkan komponen matriks laporan baru
    if "report-matrix-container" not in html_content:
        if '<div id="full-report-tab"' in html_content:
            html_content = re.sub(
                r'(<div id="full-report-tab"[^>]*>)',
                r'\1\n' + report_matrix_component,
                html_content
            )
        else:
            html_content += "\n" + report_matrix_component

        with open(report_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[SUCCESS] Indeks matriks report disematkan di {report_html_path}")

def main():
    print("=== Menjalankan Patch 4 (UI & MT4 Report Matrix Update) ===")
    update_stage2_frontend()
    update_full_report_template()
    print("=== Patch 4 Selesai Diterapkan ===")

if __name__ == '__main__':
    main()