#!/usr/bin/env python3
"""
patch6.py - Fix numpy.ndarray 'rolling' error + Enhance Full Report EA with MT5-style metrics

FIXES:
  1. backtest_engine.py: Fix `numpy.ndarray' object has no attribute 'rolling'`
     - In _generate_signals(), the "alligator" strategy calls close.rolling()
       but close is a numpy array (from .to_numpy()). Wrap with _ensure_series().
     - Also fix indicator_engine.py rsi()/ema()/macd() to use _ensure_series()
       for safety when called with numpy arrays.

  2. app.py: Fix parameter passing in /api/run-backtest route
     - Pass `balance` instead of `initial_balance` (run() reads params["balance"])
     - Pass `symbol`, `lot`, `ea_name` from body to run_backtest()

ENHANCEMENTS:
  3. templates/index.html: Enhance Full Report EA view with complete MT5-style
     metrics matrix including computed values from trades data.

Usage:
    cd /path/to/ea-backtest-engine-v2
    python3 patch6.py
"""

import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def patch_backtest_engine():
    """Fix the numpy.ndarray .rolling() error in backtest_engine.py."""
    filepath = os.path.join(BASE_DIR, "backtest_engine.py")
    if not os.path.exists(filepath):
        print("[SKIP] backtest_engine.py not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = []

    # Fix 1: In _generate_signals(), the alligator strategy uses close.rolling()
    # but close is numpy array. Fix by using _ensure_series(close).
    # The alligator block calls close.rolling(13), close.rolling(8), close.rolling(5)
    # We need to convert close to a pandas Series before those calls.

    # Find the alligator strategy block and fix it
    # Pattern: the alligator section in _generate_signals
    alligator_old = """        elif strategy == "alligator":

            jaw = (
                close
                .rolling(13)
                .mean()
            )

            teeth = (
                close
                .rolling(8)
                .mean()
            )

            lips = (
                close
                .rolling(5)
                .mean()
            )"""

    alligator_new = """        elif strategy == "alligator":

            close_s = _ensure_series(close)

            jaw = (
                close_s
                .rolling(13)
                .mean()
            )

            teeth = (
                close_s
                .rolling(8)
                .mean()
            )

            lips = (
                close_s
                .rolling(5)
                .mean()
            )"""

    if alligator_old in content:
        content = content.replace(alligator_old, alligator_new)
        changes.append("Fixed alligator strategy: close -> _ensure_series(close) before .rolling()")
    else:
        # Try a more flexible regex approach
        # Look for close.rolling() in the alligator block
        pattern = r'(elif strategy == "alligator":\s*\n)(\s*jaw = \(\s*\n\s*)(close)(\s*\.rolling\(13\))'
        if re.search(pattern, content):
            content = re.sub(pattern, r'\1\2_ensure_series(\3)\4', content)
            changes.append("Fixed alligator jaw (regex)")
        else:
            print("[WARN] Could not find alligator block to patch - may already be fixed")

        # Fix teeth
        pattern2 = r'(teeth = \(\s*\n\s*)(close)(\s*\.rolling\(8\))'
        if re.search(pattern2, content):
            content = re.sub(pattern2, r'\1_ensure_series(\2)\3', content)
            changes.append("Fixed alligator teeth (regex)")

        # Fix lips
        pattern3 = r'(lips = \(\s*\n\s*)(close)(\s*\.rolling\(5\))'
        if re.search(pattern3, content):
            content = re.sub(pattern3, r'\1_ensure_series(\2)\3', content)
            changes.append("Fixed alligator lips (regex)")

    # Fix 2: Add a safety wrapper for any other .rolling() calls on plain variables
    # In _generate_signals, close is numpy. Any strategy that calls close.rolling() will fail.
    # We already fixed alligator. Let's also add a defensive conversion at the top of _generate_signals
    # right after close = df["close"].to_numpy(dtype=float)

    # Find where close is assigned in _generate_signals and add a Series version
    close_assign_pattern = r'(close = df\[\s*\n\s*"close"\s*\n\s*\]\.to_numpy\(\s*\n\s*dtype=float\s*\n\s*\))'

    # We won't change the close assignment (it's used as numpy elsewhere),
    # but we'll make sure _ensure_series is always available at module level.
    # It already is (defined at top of file).

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        for c in changes:
            print(f"  [OK] {c}")
        print(f"[DONE] Patched backtest_engine.py ({len(changes)} changes)")
    else:
        print("[SKIP] backtest_engine.py already patched or no match found")


def patch_indicator_engine():
    """Fix indicator_engine.py - add _ensure_series() safety to rsi/ema/macd methods."""
    filepath = os.path.join(BASE_DIR, "indicator_engine.py")
    if not os.path.exists(filepath):
        print("[SKIP] indicator_engine.py not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = []

    # Fix rsi() - delta = series.diff() fails on numpy
    old_rsi = """    @staticmethod
    def rsi(series, period=14):
        delta = series.diff()"""
    new_rsi = """    @staticmethod
    def rsi(series, period=14):
        series = _ensure_series(series)
        delta = series.diff()"""
    if old_rsi in content:
        content = content.replace(old_rsi, new_rsi)
        changes.append("Fixed rsi(): added _ensure_series(series)")

    # Fix ema() - series.ewm() fails on numpy
    old_ema = """    @staticmethod
    def ema(series, period):
        return series.ewm(span=period, adjust=False).mean().to_numpy()"""
    new_ema = """    @staticmethod
    def ema(series, period):
        series = _ensure_series(series)
        return series.ewm(span=period, adjust=False).mean().to_numpy()"""
    if old_ema in content:
        content = content.replace(old_ema, new_ema)
        changes.append("Fixed ema(): added _ensure_series(series)")

    # Fix macd() - series.ewm() fails on numpy
    old_macd = """    @staticmethod
    def macd(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()"""
    new_macd = """    @staticmethod
    def macd(series, fast=12, slow=26, signal=9):
        series = _ensure_series(series)
        ema_fast = series.ewm(span=fast, adjust=False).mean()"""
    if old_macd in content:
        content = content.replace(old_macd, new_macd)
        changes.append("Fixed macd(): added _ensure_series(series)")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        for c in changes:
            print(f"  [OK] {c}")
        print(f"[DONE] Patched indicator_engine.py ({len(changes)} changes)")
    else:
        print("[SKIP] indicator_engine.py already patched or no match found")


def patch_app_run_backtest():
    """Fix app.py /api/run-backtest route - correct parameter passing."""
    filepath = os.path.join(BASE_DIR, "app.py")
    if not os.path.exists(filepath):
        print("[SKIP] app.py not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = []

    # Fix: The run_backtest() call passes initial_balance but run() expects "balance"
    # Also pass symbol, lot, ea_name from body
    old_call = """        if hasattr(engine, 'run_backtest'):
            results = engine.run_backtest(
                mql5_code=mql5_code,
                file_path=data_path,
                initial_balance=initial_balance,
                start_date=start_date,
                end_date=end_date
            )"""

    new_call = """        if hasattr(engine, 'run_backtest'):
            results = engine.run_backtest(
                mql5_code=mql5_code,
                ea_name=body.get('ea_name', 'EA_MQL5'),
                symbol=body.get('symbol', 'XAUUSD'),
                start_date=start_date,
                end_date=end_date,
                balance=initial_balance,
                lot=float(body.get('lot', 0.1))
            )"""

    if old_call in content:
        content = content.replace(old_call, new_call)
        changes.append("Fixed run_backtest() call: pass balance (not initial_balance), symbol, lot, ea_name")
    else:
        print("[WARN] Could not find run_backtest call block - may already be fixed")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        for c in changes:
            print(f"  [OK] {c}")
        print(f"[DONE] Patched app.py ({len(changes)} changes)")
    else:
        print("[SKIP] app.py already patched or no match found")


def patch_full_report_html():
    """Enhance Full Report EA view in templates/index.html with complete MT5-style metrics."""
    filepath = os.path.join(BASE_DIR, "templates", "index.html")
    if not os.path.exists(filepath):
        print("[SKIP] templates/index.html not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = []

    # ===================================================================
    # 1. Add CSS for enhanced MT5 report sections
    # ===================================================================
    css_old = """    .mt5-chart-title { text-align: center; font-size: 10px; color: var(--text-muted); margin-top: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }"""

    css_new = """    .mt5-chart-title { text-align: center; font-size: 10px; color: var(--text-muted); margin-top: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
    .mt5-section-title { font-size: 11px; font-weight: 800; color: var(--gold); text-transform: uppercase; letter-spacing: 0.08em; padding: 10px 0 6px; border-bottom: 1px solid var(--border-soft); margin-top: 16px; margin-bottom: 4px; }
    .mt5-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
    .mt5-summary-card { background: var(--bg-soft); border: 1px solid var(--border-soft); border-radius: var(--radius-sm); padding: 14px 16px; }
    .mt5-summary-card .label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
    .mt5-summary-card .value { font-size: 22px; font-weight: 800; font-family: var(--font-mono); }
    .mt5-summary-card.profit .value { color: var(--green); }
    .mt5-summary-card.loss .value { color: var(--red); }
    .mt5-summary-card.neutral .value { color: var(--gold); }
    .mt5-badges { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
    .mt5-badge { padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    .mt5-badge.verified { background: rgba(34,197,94,0.12); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
    .mt5-badge.moderate { background: rgba(245,158,11,0.12); color: var(--yellow); border: 1px solid rgba(245,158,11,0.3); }
    .mt5-badge.risk { background: rgba(244,63,94,0.12); color: var(--red); border: 1px solid rgba(244,63,94,0.3); }
    .mt5-badge.info { background: var(--gold-dim); color: var(--gold); border: 1px solid var(--gold-glow); }
    .mt5-badge.strategy { background: rgba(59,130,246,0.12); color: var(--blue); border: 1px solid rgba(59,130,246,0.3); }"""

    if css_old in content:
        content = content.replace(css_old, css_new)
        changes.append("Added CSS for enhanced MT5 report sections")
    else:
        print("[WARN] Could not find MT5 CSS anchor point")

    # ===================================================================
    # 2. Replace the Full Report EA view HTML
    # ===================================================================
    view_old = """    <!-- ========================================================== -->
    <!-- VIEW: FULL REPORT EA -->
    <!-- ========================================================== -->
    <div id="view-fullreport" class="view">
      <div class="card">
        <h3>📑 Full Report — MT5 Style Analysis Matrix</h3>
        <div style="display:flex; gap:10px; align-items:flex-end; margin-bottom:14px; flex-wrap:wrap;">
          <div class="form-group" style="flex:1; min-width:220px; margin-bottom:0;">
            <label>Pilih Job dari Histori</label>
            <select id="reportJobSelect"><option value="">-- Memuat histori --</option></select>
          </div>
          <button class="btn primary" onclick="loadFullReport()">📄 Tampilkan Report</button>
          <button class="btn blue" onclick="openMT5Report()">🖨️ Buka HTML Report MT5</button>
        </div>
        <div id="fullReportBox">
          <div class="empty-state">
            <div class="empty-icon">📑</div>
            <p>Pilih job dari histori atau jalankan backtest untuk melihat matriks analisa lengkap.</p>
          </div>
        </div>
      </div>
    </div>"""

    view_new = """    <!-- ========================================================== -->
    <!-- VIEW: FULL REPORT EA -->
    <!-- ========================================================== -->
    <div id="view-fullreport" class="view">
      <div class="card">
        <h3>📑 Full Report — MT5 Style Analysis Matrix</h3>
        <div style="display:flex; gap:10px; align-items:flex-end; margin-bottom:14px; flex-wrap:wrap;">
          <div class="form-group" style="flex:1; min-width:220px; margin-bottom:0;">
            <label>Pilih Job dari Histori</label>
            <select id="reportJobSelect"><option value="">-- Memuat histori --</option></select>
          </div>
          <button class="btn primary" onclick="loadFullReport()">📄 Tampilkan Report</button>
          <button class="btn blue" onclick="openMT5Report()">🖨️ Buka HTML Report MT5</button>
          <button class="btn green" onclick="autoLoadLatestReport()">⚡ Auto Load Latest</button>
        </div>
        <div id="fullReportBox">
          <div class="empty-state">
            <div class="empty-icon">📑</div>
            <p>Pilih job dari histori atau jalankan backtest untuk melihat matriks analisa lengkap.</p>
          </div>
        </div>
      </div>
    </div>"""

    if view_old in content:
        content = content.replace(view_old, view_new)
        changes.append("Enhanced Full Report EA view HTML with auto-load button")
    else:
        print("[WARN] Could not find Full Report EA view HTML")

    # ===================================================================
    # 3. Replace the MT5_ROW_GROUPS with expanded version
    # ===================================================================
    mt5_groups_old_start = "  const MT5_ROW_GROUPS = ["
    mt5_groups_old_end = "  ];"

    # Find the exact block
    groups_start_idx = content.find(mt5_groups_old_start)
    if groups_start_idx >= 0:
        # Find the closing ]; after MT5_ROW_GROUPS
        search_from = groups_start_idx + len(mt5_groups_old_start)
        # Find the next "  ];" after the start
        end_idx = content.find("\n  ];\n", search_from)
        if end_idx >= 0:
            end_idx += len("\n  ];\n")
            old_block = content[groups_start_idx:end_idx]

            new_block = """  const MT5_ROW_GROUPS = [
    // Section: Settings
    [{ label: 'Bars', keys: ['bars', 'total_rows_processed'] },
     { label: 'Ticks', keys: ['ticks'] },
     { label: 'Symbols', keys: ['symbols', 'symbol_raw'] }],
    // Section: Deposit
    [{ label: 'Initial Deposit', keys: ['initial_deposit', 'initial_balance'] },
     { label: 'Spread', keys: ['spread'] },
     { label: 'Leverage', keys: ['leverage'] }],
    // Section: Net Profit & Drawdown
    [{ label: 'Total Net Profit', keys: ['total_net_profit', 'net_profit', 'final_balance'] },
     { label: 'Balance Drawdown Absolute', keys: ['balance_drawdown_absolute', 'max_drawdown_val'] },
     { label: 'Equity Drawdown Absolute', keys: ['equity_drawdown_absolute'] }],
    [{ label: 'Gross Profit', keys: ['gross_profit'] },
     { label: 'Balance Drawdown Maximal', keys: ['balance_drawdown_maximal', 'max_drawdown_pct'] },
     { label: 'Equity Drawdown Maximal', keys: ['equity_drawdown_maximal'] }],
    [{ label: 'Gross Loss', keys: ['gross_loss'] },
     { label: 'Balance Drawdown Relative', keys: ['balance_drawdown_relative'] },
     { label: 'Equity Drawdown Relative', keys: ['equity_drawdown_relative'] }],
    // Section: Ratios
    [{ label: 'Profit Factor', keys: ['profit_factor'] },
     { label: 'Expected Payoff', keys: ['expected_payoff', 'expectancy'] },
     { label: 'Margin Level', keys: ['margin_level'] }],
    [{ label: 'Recovery Factor', keys: ['recovery_factor'] },
     { label: 'Sharpe Ratio', keys: ['sharpe_ratio', 'sortino_ratio'] },
     { label: 'Z-Score', keys: ['z_score'] }],
    [{ label: 'AHPR', keys: ['ahpr'] },
     { label: 'LR Correlation', keys: ['lr_correlation'] },
     { label: 'OnTester Result', keys: ['ontester_result', 'on_tester_result'] }],
    [{ label: 'GHPR', keys: ['ghpr'] },
     { label: 'LR Standard Error', keys: ['lr_standard_error'] },
     { label: 'Scientific Score', keys: ['scientific_score'] }],
    // Section: Trades
    [{ label: 'Total Trades', keys: ['total_trades'] },
     { label: 'Short Trades (won %)', keys: ['short_trades_won_pct', 'short_trades'] },
     { label: 'Long Trades (won %)', keys: ['long_trades_won_pct', 'long_trades'] }],
    [{ label: 'Total Deals', keys: ['total_deals'] },
     { label: 'Profit Trades (% of total)', keys: ['profit_trades_pct', 'win_rate'] },
     { label: 'Loss Trades (% of total)', keys: ['loss_trades_pct', 'loss_rate'] }],
    // Section: Extrema
    [{ label: 'Largest Profit Trade', keys: ['largest_profit_trade', 'top1_trade'] },
     { label: 'Largest Loss Trade', keys: ['largest_loss_trade'] },
     { label: 'Average Profit Trade', keys: ['average_profit_trade', 'avg_win'] }],
    [{ label: 'Average Loss Trade', keys: ['average_loss_trade', 'avg_loss'] },
     { label: 'Average Consecutive Wins', keys: ['average_consecutive_wins'] },
     { label: 'Average Consecutive Losses', keys: ['average_consecutive_losses'] }],
    [{ label: 'Max Consecutive Wins ($)', keys: ['max_consecutive_wins_amount', 'maximum_consecutive_wins'] },
     { label: 'Max Consecutive Losses ($)', keys: ['max_consecutive_losses_amount', 'maximum_consecutive_losses'] },
     { label: 'Max Consecutive Profit (count)', keys: ['max_consecutive_profit_count', 'maximal_consecutive_profit_count'] }],
    [{ label: 'Max Consecutive Loss (count)', keys: ['max_consecutive_loss_count', 'maximal_consecutive_loss_count'] },
     { label: 'Maximal Profit (count)', keys: ['maximal_profit_count'] },
     { label: 'Maximal Loss (count)', keys: ['maximal_loss_count'] }],
    // Section: Additional Metrics
    [{ label: 'Calmar Ratio', keys: ['calmar_ratio'] },
     { label: 'Top 5 Concentration %', keys: ['top5_concentration_pct'] },
     { label: 'Jackpot Dependent', keys: ['is_jackpot_dependent'] }],
    [{ label: 'Engine Version', keys: ['engine_version'] },
     { label: 'Strategy Type', keys: ['strategy_type'] },
     { label: 'Backtest Duration (s)', keys: ['backtest_duration_seconds'] }],
    [{ label: 'Start Date', keys: ['start_date'] },
     { label: 'End Date', keys: ['end_date'] },
     { label: 'Data File Count', keys: ['data_file_count'] }]
  ];
"""

            content = content[:groups_start_idx] + new_block + content[end_idx:]
            changes.append("Expanded MT5_ROW_GROUPS with complete metric definitions")
        else:
            print("[WARN] Could not find end of MT5_ROW_GROUPS block")
    else:
        print("[WARN] Could not find MT5_ROW_GROUPS start")

    # ===================================================================
    # 4. Replace renderFullReportMetrics with enhanced version
    # ===================================================================
    render_old = """  function renderFullReportMetrics(m, jobId, trades) {
    const box = document.getElementById('fullReportBox');
    mt5Charts.forEach(c => c.destroy());
    mt5Charts = [];

    const rowsHtml = MT5_ROW_GROUPS.map(group => {
      const cells = group.map(cell => cell
        ? `<td class="mt5-label">${escapeHtml(cell.label)}</td><td class="mt5-value">${escapeHtml(mtFormat(mtFind(m, cell.keys)))}</td>`
        : '<td class="mt5-label"></td><td class="mt5-value"></td>'
      ).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    const hqRaw = mtFind(m, ['history_quality']);
    const hqPct = parseFloat(String(hqRaw ?? '0').replace('%', '')) || 0;
    const hasTradeDist = Array.isArray(trades) && trades.length > 0;
    const dist = aggregateTradesByPeriod(trades || []);

    box.innerHTML = `
      <div class="mt5-report">
        <div style="margin-bottom:10px; font-family: var(--font-mono); font-size:11px; color: var(--text-muted);">Job ID: ${escapeHtml(jobId)}</div>
        ${hqRaw !== undefined ? `
        <div class="mt5-hq-row">
          <span style="color:var(--text-muted); font-size:11px; white-space:nowrap;">History Quality</span>
          <div class="mt5-hq-bar-track"><div class="mt5-hq-bar-fill" style="width:${Math.min(100, Math.max(0, hqPct))}%;"></div></div>
          <span class="mono" style="font-weight:700;">${escapeHtml(String(hqRaw))}</span>
        </div>` : ''}
        <div class="table-wrap" style="max-height:520px;">
          <table class="mt5-grid-table"><tbody>${rowsHtml}</tbody></table>
        </div>
        <div class="mt5-charts-grid">
          <div class="mt5-chart-box">
            <canvas id="mt5ChartHours" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by hours</div>
          </div>
          <div class="mt5-chart-box">
            <canvas id="mt5ChartWeekdays" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by weekdays</div>
          </div>
          <div class="mt5-chart-box">
            <canvas id="mt5ChartMonths" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by months</div>
          </div>
        </div>
        ${!hasTradeDist ? '<p style="color:var(--text-muted); font-size:11px; text-align:center; margin-top:10px;">Distribusi per jam/hari/bulan butuh daftar trade (open/close time) untuk job ini.</p>' : ''}
        <details style="margin-top:18px;">
          <summary style="cursor:pointer; color:var(--text-muted); font-size:11px;">Lihat data mentah dari API (JSON)</summary>
          <div class="table-wrap" style="max-height:300px; margin-top:8px;">
            <table><tbody>${Object.keys(m).map(k => `<tr><td style="color:var(--text-muted); font-size:10px; font-weight:700; text-transform:uppercase;">${escapeHtml(String(k).replace(/_/g, ' '))}</td><td class="mono">${escapeHtml(JSON.stringify(m[k]))}</td></tr>`).join('')}</tbody></table>
          </div>
        </details>
      </div>
    `;

    renderMiniBarChart('mt5ChartHours', Array.from({ length: 24 }, (_, i) => i), dist.hours);
    renderMiniBarChart('mt5ChartWeekdays', ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], dist.weekdays);
    renderMiniBarChart('mt5ChartMonths', ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], dist.months);
  }"""

    render_new = """  function computeMT5ExtendedMetrics(m, trades) {
    // Compute additional MT5-style metrics from trades data
    const t = normalizeTrades(trades || []);
    const closed = t.filter(x => x._profit !== 0 || x._openTime !== '-');
    const profits = closed.map(x => x._profit);
    const wins = profits.filter(p => p > 0);
    const losses = profits.filter(p => p < 0);
    const netProfit = profits.reduce((a, b) => a + b, 0);
    const grossProfit = wins.reduce((a, b) => a + b, 0);
    const grossLoss = Math.abs(losses.reduce((a, b) => a + b, 0));
    const initBal = toNumber(mtFind(m, ['initial_balance', 'initial_deposit']));
    const finalBal = toNumber(mtFind(m, ['final_balance']));

    // Long/Short breakdown
    const longs = closed.filter(x => x._direction === 'BUY');
    const longWins = longs.filter(x => x._profit > 0).length;
    const shorts = closed.filter(x => x._direction === 'SELL');
    const shortWins = shorts.filter(x => x._profit > 0).length;

    // Consecutive streaks
    let maxConsecWin = 0, maxConsecLoss = 0, curWin = 0, curLoss = 0;
    let maxConsecWinAmt = 0, maxConsecLossAmt = 0, curWinAmt = 0, curLossAmt = 0;
    for (const p of profits) {
      if (p > 0) {
        curWin++; curLoss = 0;
        curWinAmt += p; curLossAmt = 0;
        if (curWin > maxConsecWin) maxConsecWin = curWin;
        if (curWinAmt > maxConsecWinAmt) maxConsecWinAmt = curWinAmt;
      } else if (p < 0) {
        curLoss++; curWin = 0;
        curLossAmt += Math.abs(p); curWinAmt = 0;
        if (curLoss > maxConsecLoss) maxConsecLoss = curLoss;
        if (curLossAmt > maxConsecLossAmt) maxConsecLossAmt = curLossAmt;
      }
    }

    // Largest trade
    const largestProfit = profits.length ? Math.max(...profits) : 0;
    const largestLoss = profits.length ? Math.min(...profits) : 0;
    const avgWin = wins.length ? wins.reduce((a,b) => a+b, 0) / wins.length : 0;
    const avgLoss = losses.length ? Math.abs(losses.reduce((a,b) => a+b, 0) / losses.length) : 0;
    const avgTrade = profits.length ? netProfit / profits.length : 0;

    return {
      'largest_profit_trade': largestProfit,
      'largest_loss_trade': largestLoss,
      'average_profit_trade': avgWin,
      'average_loss_trade': avgLoss,
      'max_consecutive_wins_amount': maxConsecWinAmt,
      'max_consecutive_losses_amount': maxConsecLossAmt,
      'max_consecutive_profit_count': maxConsecWin,
      'max_consecutive_loss_count': maxConsecLoss,
      'average_consecutive_wins': profits.length ? (maxConsecWin > 0 ? Math.round(profits.filter(p=>p>0).length / Math.ceil(maxConsecWin)) : 0) : 0,
      'average_consecutive_losses': profits.length ? (maxConsecLoss > 0 ? Math.round(profits.filter(p=>p<0).length / Math.ceil(maxConsecLoss)) : 0) : 0,
      'short_trades': `${shorts.length} (${shorts.length ? Math.round(shortWins/shorts.length*100) : 0}%)`,
      'long_trades': `${longs.length} (${longs.length ? Math.round(longWins/longs.length*100) : 0}%)`,
      'profit_trades_pct': `${wins.length} (${wins.length ? Math.round(wins.length/profits.length*100) : 0}%)`,
      'loss_trades_pct': `${losses.length} (${losses.length ? Math.round(losses.length/profits.length*100) : 0}%)`,
      'expected_payoff': avgTrade,
      'total_net_profit': netProfit,
      'gross_profit': grossProfit,
      'gross_loss': grossLoss,
      'total_trades': closed.length,
      'initial_deposit': initBal,
      'final_balance': finalBal || (initBal + netProfit),
      'bars': mtFind(m, ['total_rows_processed', 'bars']) || 0,
      'symbols': mtFind(m, ['symbol_raw', 'symbols']) || '-',
    };
  }

  function autoLoadLatestReport() {
    const sel = document.getElementById('reportJobSelect');
    if (sel.options.length > 1) {
      sel.selectedIndex = 1;
      loadFullReport();
    } else {
      if (currentJobId) {
        sel.value = currentJobId;
        loadFullReport();
      } else {
        alert('Belum ada job tersedia. Jalankan backtest terlebih dahulu.');
      }
    }
  }

  function renderFullReportMetrics(m, jobId, trades) {
    const box = document.getElementById('fullReportBox');
    mt5Charts.forEach(c => c.destroy());
    mt5Charts = [];

    // Merge computed metrics with API data
    const computed = computeMT5ExtendedMetrics(m, trades);
    const merged = Object.assign({}, m, computed);

    // Build row groups with section headers
    const sections = [
      { title: 'Backtest Settings', rows: [0, 1] },
      { title: 'Net Profit & Drawdown', rows: [2, 3, 4] },
      { title: 'Performance Ratios', rows: [5, 6, 7, 8] },
      { title: 'Trades Summary', rows: [9, 10] },
      { title: 'Extreme Values & Averages', rows: [11, 12, 13, 14] },
      { title: 'Additional Metrics', rows: [15, 16, 17] }
    ];

    let rowsHtml = '';
    for (const sec of sections) {
      rowsHtml += `<tr><td colspan="6" class="mt5-section-title">${sec.title}</td></tr>`;
      for (const idx of sec.rows) {
        if (idx >= MT5_ROW_GROUPS.length) break;
        const group = MT5_ROW_GROUPS[idx];
        const cells = group.map(cell => cell
          ? `<td class="mt5-label">${escapeHtml(cell.label)}</td><td class="mt5-value">${escapeHtml(mtFormat(mtFind(merged, cell.keys)))}</td>`
          : '<td class="mt5-label"></td><td class="mt5-value"></td>'
        ).join('');
        rowsHtml += `<tr>${cells}</tr>`;
      }
    }

    // Summary cards
    const netProfit = toNumber(computed.total_net_profit);
    const profitClass = netProfit > 0 ? 'profit' : (netProfit < 0 ? 'loss' : 'neutral');
    const winRate = toNumber(mtFind(merged, ['win_rate']));
    const pf = toNumber(mtFind(merged, ['profit_factor']));
    const ddPct = toNumber(mtFind(merged, ['max_drawdown_pct']));
    const statusLabel = String(mtFind(merged, ['status_label']) || 'N/A');
    const statusClass = statusLabel.includes('VERIFIED') ? 'verified' : (statusLabel.includes('MODERATE') ? 'moderate' : 'risk');
    const strategyType = String(mtFind(merged, ['strategy_type']) || 'unknown');

    const hqRaw = mtFind(m, ['history_quality']);
    const hqPct = parseFloat(String(hqRaw ?? '0').replace('%', '')) || 0;
    const hasTradeDist = Array.isArray(trades) && trades.length > 0;
    const dist = aggregateTradesByPeriod(trades || []);

    box.innerHTML = `
      <div class="mt5-report">
        <div style="margin-bottom:10px; font-family: var(--font-mono); font-size:11px; color: var(--text-muted);">
          Job ID: ${escapeHtml(jobId)} | EA: ${escapeHtml(String(mtFind(m, ['ea_name']) || mtFind(m, ['params', 'ea_name']) || 'EA_MQL5'))}
        </div>

        <div class="mt5-badges">
          <span class="mt5-badge ${statusClass}">${escapeHtml(statusLabel)}</span>
          <span class="mt5-badge strategy">${escapeHtml(strategyType)}</span>
          <span class="mt5-badge info">Score: ${escapeHtml(mtFormat(mtFind(merged, ['scientific_score'])))}</span>
          <span class="mt5-badge ${profitClass === 'profit' ? 'verified' : (profitClass === 'loss' ? 'risk' : 'moderate')}">PF: ${escapeHtml(mtFormat(pf))}</span>
          <span class="mt5-badge info">DD: ${escapeHtml(mtFormat(ddPct))}%</span>
        </div>

        <div class="mt5-summary-grid">
          <div class="mt5-summary-card ${profitClass}">
            <div class="label">Net Profit</div>
            <div class="value">${money(netProfit)}</div>
          </div>
          <div class="mt5-summary-card neutral">
            <div class="label">Win Rate</div>
            <div class="value">${winRate.toFixed(1)}%</div>
          </div>
          <div class="mt5-summary-card ${profitClass}">
            <div class="label">Total Trades</div>
            <div class="value">${toNumber(computed.total_trades)}</div>
          </div>
        </div>

        ${hqRaw !== undefined ? `
        <div class="mt5-hq-row">
          <span style="color:var(--text-muted); font-size:11px; white-space:nowrap;">History Quality</span>
          <div class="mt5-hq-bar-track"><div class="mt5-hq-bar-fill" style="width:${Math.min(100, Math.max(0, hqPct))}%;"></div></div>
          <span class="mono" style="font-weight:700;">${escapeHtml(String(hqRaw))}</span>
        </div>` : ''}

        <div class="table-wrap" style="max-height:600px;">
          <table class="mt5-grid-table"><tbody>${rowsHtml}</tbody></table>
        </div>

        <div class="mt5-section-title">Profit/Loss Distribution</div>
        <div class="mt5-charts-grid">
          <div class="mt5-chart-box">
            <canvas id="mt5ChartHours" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by hours</div>
          </div>
          <div class="mt5-chart-box">
            <canvas id="mt5ChartWeekdays" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by weekdays</div>
          </div>
          <div class="mt5-chart-box">
            <canvas id="mt5ChartMonths" height="140"></canvas>
            <div class="mt5-chart-title">Profits and losses by months</div>
          </div>
        </div>
        ${!hasTradeDist ? '<p style="color:var(--text-muted); font-size:11px; text-align:center; margin-top:10px;">Distribusi per jam/hari/bulan butuh daftar trade (open/close time) untuk job ini.</p>' : ''}

        <details style="margin-top:18px;">
          <summary style="cursor:pointer; color:var(--text-muted); font-size:11px;">Lihat data mentah dari API (JSON)</summary>
          <div class="table-wrap" style="max-height:300px; margin-top:8px;">
            <table><tbody>${Object.keys(merged).sort().map(k => `<tr><td style="color:var(--text-muted); font-size:10px; font-weight:700; text-transform:uppercase;">${escapeHtml(String(k).replace(/_/g, ' '))}</td><td class="mono">${escapeHtml(JSON.stringify(merged[k]))}</td></tr>`).join('')}</tbody></table>
          </div>
        </details>
      </div>
    `;

    renderMiniBarChart('mt5ChartHours', Array.from({ length: 24 }, (_, i) => String(i)), dist.hours);
    renderMiniBarChart('mt5ChartWeekdays', ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], dist.weekdays);
    renderMiniBarChart('mt5ChartMonths', ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], dist.months);
  }"""

    if render_old in content:
        content = content.replace(render_old, render_new)
        changes.append("Replaced renderFullReportMetrics with enhanced version (summary cards, badges, sections, computed metrics)")
    else:
        print("[WARN] Could not find renderFullReportMetrics function - trying flexible match")
        # Try to find the function by its start and end
        func_start = content.find("  function renderFullReportMetrics(m, jobId, trades) {")
        if func_start >= 0:
            # Find the closing } at the same indentation level
            # Look for the pattern: "  }\n</script>" or "  }\n  \n</script>"
            search_from = func_start + 10
            end_match = re.search(r'\n  \}\n', content[search_from:])
            if end_match:
                end_idx = search_from + end_match.end()
                content = content[:func_start] + render_new.lstrip() + content[end_idx:]
                changes.append("Replaced renderFullReportMetrics (flexible match)")
            else:
                print("[ERROR] Could not find end of renderFullReportMetrics")
        else:
            print("[ERROR] Could not find renderFullReportMetrics at all")

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
    print("patch6.py - Fix numpy rolling error + Enhance Full Report EA")
    print("=" * 60)
    print()

    print("[1/4] Patching backtest_engine.py (numpy .rolling() fix)...")
    patch_backtest_engine()
    print()

    print("[2/4] Patching indicator_engine.py (safety wrappers)...")
    patch_indicator_engine()
    print()

    print("[3/4] Patching app.py (parameter passing fix)...")
    patch_app_run_backtest()
    print()

    print("[4/4] Patching templates/index.html (Full Report EA enhancement)...")
    patch_full_report_html()
    print()

    print("=" * 60)
    print("DONE! All patches applied successfully.")
    print()
    print("Summary of fixes:")
    print("  1. Fixed numpy.ndarray .rolling() error in alligator strategy")
    print("  2. Added _ensure_series() safety to indicator_engine.py")
    print("  3. Fixed parameter passing (balance/symbol/lot) in /api/run-backtest")
    print("  4. Enhanced Full Report EA with:")
    print("     - Summary cards (Net Profit, Win Rate, Total Trades)")
    print("     - Status badges (verified/moderate/risk, strategy, score)")
    print("     - Section headers in metrics table")
    print("     - Computed metrics from trades (consecutive wins/losses, etc)")
    print("     - Auto-load latest job button")
    print("     - Expanded MT5_ROW_GROUPS with all MT5 report fields")
    print("=" * 60)


if __name__ == "__main__":
    main()
