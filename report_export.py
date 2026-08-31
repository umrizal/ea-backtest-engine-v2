# ============================================================
# report_export.py
# Pintarin Laboratorium EA – Stage 3
#
# Export hasil backtest ke HTML (enhanced) + JSON + push Google Sheet
# ============================================================

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


class ReportExporter:
    """Enhanced report generator + optional Sheet sync."""

    @staticmethod
    def to_html(job_id: str, result: Dict[str, Any], title: str = "Strategy Tester Report") -> str:
        m = result.get("metrics") or result.get("report") or result
        if not isinstance(m, dict):
            m = {}

        trades = result.get("trades") or m.get("trades") or []
        score = m.get("scientific_score", 0)
        status = m.get("status_label", "N/A")
        status_color = (
            "#10b981" if score and float(score) >= 80
            else "#f59e0b" if score and float(score) >= 60
            else "#f43f5e"
        )

        rows = ""
        for t in trades[-50:]:
            profit = float(t.get("profit") or 0)
            color = "#10b981" if profit >= 0 else "#f43f5e"
            rows += f"""
            <tr>
              <td>{t.get('open_time') or t.get('entry_time') or ''}</td>
              <td>{t.get('close_time') or ''}</td>
              <td><b>{t.get('direction') or t.get('type') or ''}</b></td>
              <td>{t.get('entry_price') or t.get('price') or ''}</td>
              <td>{t.get('close_price') or ''}</td>
              <td>{t.get('lot') or ''}</td>
              <td style="color:{color};font-weight:700">${profit:.2f}</td>
              <td>{t.get('comment') or t.get('reason') or ''}</td>
            </tr>"""

        risk_banner = ""
        if m.get("is_jackpot_dependent"):
            risk_banner = f"""
            <div class="banner">
              ⚠️ JACKPOT DEPENDENT — Top-5 trades = {m.get('top5_concentration_pct', 0)}% of profit.
              Strategi berisiko overfitting.
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>{title} — {job_id[:8]}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; background:#070a10; color:#e2e8f0; padding:24px; }}
    .card {{ background:#0d131f; border:1px solid #1a2436; border-radius:10px; padding:18px; margin-bottom:18px; }}
    h1 {{ color:#d9a75c; font-size:22px; margin:0 0 8px; }}
    h2 {{ color:#94a3b8; font-size:14px; text-transform:uppercase; letter-spacing:.08em; }}
    .kpi {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
    .kpi .item {{ background:#0a101c; border-radius:8px; padding:12px; text-align:center; }}
    .kpi .label {{ font-size:10px; color:#64748b; font-weight:700; }}
    .kpi .val {{ font-size:18px; font-weight:800; color:#d9a75c; margin-top:4px; font-family:monospace; }}
    .status {{ display:inline-block; padding:4px 12px; border-radius:999px; background:{status_color}22; color:{status_color}; font-weight:700; font-size:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th, td {{ padding:8px 10px; border-bottom:1px solid #1a2436; text-align:left; }}
    th {{ color:#64748b; background:#070c14; }}
    .banner {{ background:rgba(244,63,94,.12); border:1px solid rgba(244,63,94,.35); color:#fda4af;
               padding:10px 14px; border-radius:8px; margin-bottom:16px; font-size:12px; font-weight:600; }}
    .meta {{ color:#64748b; font-size:11px; margin-top:8px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <span class="status">{status}</span>
    <p class="meta">Job: {job_id} · Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  </div>

  {risk_banner}

  <div class="card">
    <h2>Key Performance Indicators</h2>
    <div class="kpi">
      <div class="item"><div class="label">Net Profit</div><div class="val">${float(m.get('net_profit') or 0):.2f}</div></div>
      <div class="item"><div class="label">Profit Factor</div><div class="val">{float(m.get('profit_factor') or 0):.2f}</div></div>
      <div class="item"><div class="label">Win Rate</div><div class="val">{float(m.get('win_rate') or 0):.1f}%</div></div>
      <div class="item"><div class="label">Max Drawdown</div><div class="val">{float(m.get('max_drawdown_pct') or 0):.2f}%</div></div>
      <div class="item"><div class="label">Sortino</div><div class="val">{float(m.get('sortino_ratio') or 0):.2f}</div></div>
      <div class="item"><div class="label">Expectancy</div><div class="val">${float(m.get('expectancy') or 0):.2f}</div></div>
      <div class="item"><div class="label">Scientific Score</div><div class="val">{float(m.get('scientific_score') or 0):.1f}</div></div>
      <div class="item"><div class="label">Total Trades</div><div class="val">{int(m.get('total_trades') or 0)}</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Trade History (last 50)</h2>
    <table>
      <thead>
        <tr>
          <th>Open</th><th>Close</th><th>Dir</th><th>Entry</th><th>Exit</th>
          <th>Lot</th><th>Profit</th><th>Reason</th>
        </tr>
      </thead>
      <tbody>{rows or '<tr><td colspan="8">No trades</td></tr>'}</tbody>
    </table>
  </div>
</body>
</html>"""
        return html

    @staticmethod
    def to_json(result: Dict[str, Any]) -> str:
        def default(o):
            if hasattr(o, "isoformat"):
                return o.isoformat()
            return str(o)
        return json.dumps(result, indent=2, default=default)

    @staticmethod
    def save_html(job_id: str, result: Dict, out_dir: str = "reports") -> str:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"report_{job_id[:8]}.html")
        html = ReportExporter.to_html(job_id, result)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path

    @staticmethod
    def push_to_sheet(result: Dict, sheet_sync=None) -> bool:
        if sheet_sync is None:
            try:
                from sheet_sync import SheetSyncManager
                sheet_sync = SheetSyncManager()
            except Exception:
                return False
        m = result.get("metrics") or result
        payload = {
            "type": "backtest_summary",
            "timestamp": datetime.now().isoformat(),
            "net_profit": m.get("net_profit"),
            "profit_factor": m.get("profit_factor"),
            "win_rate": m.get("win_rate"),
            "max_drawdown_pct": m.get("max_drawdown_pct"),
            "scientific_score": m.get("scientific_score"),
            "status_label": m.get("status_label"),
            "total_trades": m.get("total_trades"),
        }
        try:
            if hasattr(sheet_sync, "push_trade_async"):
                sheet_sync.push_trade_async(payload)
                return True
        except Exception as e:
            print(f"[ReportExport] Sheet push failed: {e}")
        return False
