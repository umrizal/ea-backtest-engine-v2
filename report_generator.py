class ReportGenerator:
    @staticmethod
    def generate_html_report(job_id, result, params=None):
        """Generate MT5-style HTML report.

        Args:
            job_id: Job identifier string.
            result: Backtest result dict (metrics + trades + equity_curve).
            params: Optional dict of backtest parameters (symbol, balance, etc).

        Returns:
            HTML string.
        """
        params = params or {}

        # --- Trade history table (last 50 trades) ---
        trades_html = ""
        for t in result.get("trades", [])[-50:]:
            direction = t.get("arah") or t.get("direction") or t.get("type") or "-"
            entry = t.get("harga_entry") or t.get("entry") or t.get("entry_price") or "-"
            profit = t.get("profit", 0)
            profit_color = "#22c55e" if profit >= 0 else "#f43f5e"
            trades_html += f"""
            <tr>
                <td>{t.get('open_time', '-')}</td>
                <td>{t.get('order_id', '-')}</td>
                <td><b>{direction}</b></td>
                <td>{entry}</td>
                <td>{t.get('comment', '-')}</td>
                <td style="color:{profit_color}">${profit}</td>
            </tr>
            """

        # --- Compute additional metrics from trades ---
        trades_list = result.get("trades", [])
        profits = [t.get("profit", 0) for t in trades_list if t.get("status") == "closed"]
        total_trades = len(profits)
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        win_rate = (len(wins) / total_trades * 100) if total_trades else 0
        avg_win = (sum(wins) / len(wins)) if wins else 0
        avg_loss = (abs(sum(losses)) / len(losses)) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # Consecutive streaks
        max_consec_win = 0
        max_consec_loss = 0
        cur_win = 0
        cur_loss = 0
        for p in profits:
            if p > 0:
                cur_win += 1
                cur_loss = 0
                if cur_win > max_consec_win:
                    max_consec_win = cur_win
            elif p < 0:
                cur_loss += 1
                cur_win = 0
                if cur_loss > max_consec_loss:
                    max_consec_loss = cur_loss

        # --- Metric rows helper ---
        def metric_row(label, value, extra=""):
            return f"<tr><td class='lbl'>{label}</td><td class='val'>{value}</td><td class='lbl'>{extra}</td><td class='val'></td></tr>"

        def fmt(v):
            if v is None or v == "":
                return "-"
            if isinstance(v, float):
                return f"{v:,.2f}"
            return str(v)

        net_profit = result.get("net_profit", 0)
        profit_factor = result.get("profit_factor", 0)
        sortino = result.get("sortino_ratio", 0)
        max_dd = result.get("max_drawdown_pct", 0)
        calmar = result.get("calmar_ratio", 0)
        recovery = result.get("recovery_factor", 0)
        expectancy = result.get("expectancy", 0)
        score = result.get("scientific_score", 0)
        status = result.get("status_label", "N/A")
        init_bal = result.get("initial_balance", params.get("balance", 10000))
        final_bal = result.get("final_balance", 0)
        symbol = result.get("symbol_raw", params.get("symbol", "XAUUSD"))
        strategy = result.get("strategy_type", "unknown")
        ea_name = params.get("ea_name", "EA_MQL5")
        start_date = result.get("start_date", params.get("start_date", "-"))
        end_date = result.get("end_date", params.get("end_date", "-"))

        status_color = "#22c55e" if "VERIFIED" in str(status).upper() else ("#f59e0b" if "MODERATE" in str(status).upper() else "#f43f5e")

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Pintarin Laboratorium - Strategy Tester Report</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #070a10; color: #e2e8f0; padding: 24px; }}
                .header {{ text-align: center; margin-bottom: 24px; padding-bottom: 18px; border-bottom: 2px solid #d9a75c; }}
                .header h1 {{ color: #d9a75c; font-size: 22px; letter-spacing: 0.06em; }}
                .header p {{ color: #64748b; font-size: 12px; margin-top: 4px; }}
                .badges {{ display: flex; gap: 8px; justify-content: center; margin-top: 10px; flex-wrap: wrap; }}
                .badge {{ padding: 3px 10px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }}
                .badge.status {{ background: {status_color}22; color: {status_color}; border: 1px solid {status_color}55; }}
                .badge.strategy {{ background: #3b82f622; color: #3b82f6; border: 1px solid #3b82f655; }}
                .badge.score {{ background: #d9a75c22; color: #d9a75c; border: 1px solid #d9a75c55; }}

                .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
                .summary-card {{ background: #0d131f; border: 1px solid #1a2436; border-radius: 8px; padding: 14px; }}
                .summary-card .label {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }}
                .summary-card .value {{ font-size: 20px; font-weight: 800; font-family: 'Courier New', monospace; }}

                .card {{ background: #0d131f; border: 1px solid #1a2436; padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
                .card h2 {{ color: #d9a75c; font-size: 14px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
                .card h3 {{ color: #94a3b8; font-size: 12px; margin-bottom: 8px; }}

                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 7px 10px; border-bottom: 1px solid #1a2436; text-align: left; font-size: 12px; }}
                th {{ color: #64748b; background: #070c14; text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; }}
                td.lbl {{ color: #64748b; width: 25%; font-size: 11px; }}
                td.val {{ color: #e2e8f0; font-weight: 700; text-align: right; width: 25%; }}
                .profit {{ color: #22c55e; }}
                .loss {{ color: #f43f5e; }}
                .neutral {{ color: #d9a75c; }}

                .footer {{ text-align: center; color: #64748b; font-size: 10px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #1a2436; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚡ PINTARIN LABORATORIUM</h1>
                <p>Strategy Tester Report — EA Backtest Engine v3.0</p>
                <div class="badges">
                    <span class="badge status">{status}</span>
                    <span class="badge strategy">{strategy}</span>
                    <span class="badge score">Score: {fmt(score)}/100</span>
                </div>
            </div>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Net Profit</div>
                    <div class="value {'profit' if net_profit >= 0 else 'loss'}">${net_profit:,.2f}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Profit Factor</div>
                    <div class="value neutral">{fmt(profit_factor)}</div>
                </div>
                <div class="summary-card">
                    <div class="label">Win Rate</div>
                    <div class="value {'profit' if win_rate >= 50 else 'loss'}">{win_rate:.1f}%</div>
                </div>
                <div class="summary-card">
                    <div class="label">Total Trades</div>
                    <div class="value neutral">{total_trades}</div>
                </div>
            </div>

            <div class="card">
                <h2>📊 Backtest Settings</h2>
                <table>
                    <tr><td class="lbl">EA Name</td><td class="val">{ea_name}</td><td class="lbl">Symbol</td><td class="val">{symbol}</td></tr>
                    <tr><td class="lbl">Strategy Type</td><td class="val">{strategy}</td><td class="lbl">Period</td><td class="val">{start_date} → {end_date}</td></tr>
                    <tr><td class="lbl">Initial Deposit</td><td class="val">${fmt(init_bal)}</td><td class="lbl">Final Balance</td><td class="val">${fmt(final_bal)}</td></tr>
                    <tr><td class="lbl">Job ID</td><td class="val">{job_id}</td><td class="lbl">Bars Processed</td><td class="val">{fmt(result.get('total_rows_processed', 0))}</td></tr>
                </table>
            </div>

            <div class="card">
                <h2>💰 Profit & Drawdown</h2>
                <table>
                    {metric_row('Total Net Profit', f'${net_profit:,.2f}', 'Gross Profit', f'${gross_profit:,.2f}')}
                    {metric_row('Gross Loss', f'${gross_loss:,.2f}', 'Balance Drawdown Max', f'{fmt(max_dd)}%')}
                    {metric_row('Profit Factor', fmt(profit_factor), 'Recovery Factor', fmt(recovery))}
                    {metric_row('Expected Payoff', fmt(expectancy), 'Calmar Ratio', fmt(calmar))}
                </table>
            </div>

            <div class="card">
                <h2>📈 Performance Ratios</h2>
                <table>
                    {metric_row('Sortino Ratio', fmt(sortino), 'Win Rate', f'{win_rate:.1f}%')}
                    {metric_row('Loss Rate', f'{100 - win_rate:.1f}%', 'Scientific Score', f'{fmt(score)}/100')}
                    {metric_row('Status', status, 'Engine Version', fmt(result.get('engine_version', '3.0.0')))}
                    {metric_row('Backtest Duration (s)', fmt(result.get('backtest_duration_seconds', 0)), 'Data Files', fmt(result.get('data_file_count', 0)))}
                </table>
            </div>

            <div class="card">
                <h2>🎯 Trade Statistics</h2>
                <table>
                    {metric_row('Total Trades', total_trades, 'Profit Trades', f'{len(wins)} ({len(wins)/total_trades*100:.1f}%)' if total_trades else '0 (0%)')}
                    {metric_row('Loss Trades', f'{len(losses)} ({len(losses)/total_trades*100:.1f}%)' if total_trades else '0 (0%)', 'Largest Profit', f'${largest_win:,.2f}')}
                    {metric_row('Largest Loss', f'${largest_loss:,.2f}', 'Average Profit', f'${avg_win:,.2f}')}
                    {metric_row('Average Loss', f'${avg_loss:,.2f}', 'Max Consecutive Wins', max_consec_win)}
                    {metric_row('Max Consecutive Losses', max_consec_loss, 'Top 5 Concentration', f'{fmt(result.get("top5_concentration_pct", 0))}%')}
                </table>
            </div>

            <div class="card">
                <h2>📋 Trade History (Last 50)</h2>
                <table>
                    <thead><tr><th>Time</th><th>Order ID</th><th>Type</th><th>Price</th><th>Comment</th><th>Profit</th></tr></thead>
                    <tbody>{trades_html or '<tr><td colspan="6" style="text-align:center;color:#64748b;">No trades</td></tr>'}</tbody>
                </table>
            </div>

            <div class="footer">
                Generated by Pintarin Laboratorium EA Backtest Engine v3.0<br>
                Job ID: {job_id} | Generated at: {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            </div>
        </body>
        </html>
        """
        return html
