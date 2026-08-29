class ReportGenerator:
    @staticmethod
    def generate_html_report(job_id, result):
        trades_html = ""
        for t in result.get("trades", [])[-30:]: # Render last 30 trades
            trades_html += f"""
            <tr>
                <td>{t['open_time']}</td>
                <td>{t['order_id']}</td>
                <td><b>{t['arah']}</b></td>
                <td>{t['harga_entry']}</td>
                <td>{t['comment']}</td>
                <td style="color:{'#10b981' if t['profit']>=0 else '#f43f5e'}">${t['profit']}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Strategy Tester Report - {job_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: #070a10; color: #e2e8f0; padding: 20px; }}
                .card {{ background: #0d131f; border: 1px solid #1a2436; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                h2 {{ color: #d9a75c; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; border-bottom: 1px solid #1a2436; text-align: left; }}
                th {{ color: #64748b; background: #070c14; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Strategy Tester Report: {result.get('status_label', 'N/A')}</h2>
                <p><b>Net Profit:</b> ${result.get('net_profit', 0)} | <b>Profit Factor:</b> {result.get('profit_factor', 0)} | <b>Win Rate:</b> {result.get('win_rate', 0)}%</p>
                <p><b>Sortino Ratio:</b> {result.get('sortino_ratio', 0)} | <b>Max Drawdown:</b> {result.get('max_drawdown_pct', 0)}%</p>
            </div>
            <div class="card">
                <h3>Trade History</h3>
                <table>
                    <thead><tr><th>Time</th><th>Order ID</th><th>Type</th><th>Price</th><th>Comment</th><th>Profit</th></tr></thead>
                    <tbody>{trades_html}</tbody>
                </table>
            </div>
        </body>
        </html>
        """
        return html
