/**
 * stage3_frontend.js
 * Pintarin Laboratorium EA – Stage 3 UI
 *
 * - Condition Builder (preset + custom rules)
 * - Walk-Forward runner + result table
 * - Monte Carlo runner
 * - Portfolio compare (simple multi-item)
 * - Export report HTML
 *
 * Load after stage2_frontend.js
 */

(function (window) {
  "use strict";

  // ----------------------------------------------------------
  // API
  // ----------------------------------------------------------
  async function getPresets() {
    const r = await fetch("/api/conditions/presets");
    return r.json();
  }

  async function previewConditions(rules, opts = {}) {
    const r = await fetch("/api/conditions/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules, ...opts }),
    });
    return r.json();
  }

  async function startWalkForward(payload) {
    const r = await fetch("/api/walkforward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return r.json();
  }

  async function startMonteCarlo(payload) {
    const r = await fetch("/api/montecarlo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return r.json();
  }

  async function startPortfolio(items) {
    const r = await fetch("/api/portfolio/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    return r.json();
  }

  async function pollJob(jobId, onProgress) {
    for (let i = 0; i < 120; i++) {
      const st = await fetch(`/api/stage3/status/${jobId}`).then((x) => x.json());
      if (onProgress) onProgress(st.progress || 0, st.status);
      if (st.status === "completed") {
        const res = await fetch(`/api/stage3/result/${jobId}`).then((x) => x.json());
        return res;
      }
      if (st.status === "failed") {
        throw new Error(st.error || "Job failed");
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
    throw new Error("Timeout menunggu job");
  }

  async function exportReport(result, jobId, pushSheet = false) {
    const r = await fetch("/api/report/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result, job_id: jobId, format: "html", push_sheet: pushSheet }),
    });
    return r.json();
  }

  // ----------------------------------------------------------
  // UI: Stage 3 Panel
  // ----------------------------------------------------------

  function ensurePanel() {
    let panel = document.getElementById("stage3-panel");
    if (panel) return panel;

    panel = document.createElement("div");
    panel.id = "stage3-panel";
    panel.className = "card";
    panel.style.marginTop = "16px";
    panel.innerHTML = `
      <h3>🧪 Stage 3 — Lab Tools</h3>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
        <button class="btn" id="s3-btn-conditions">📐 Condition Builder</button>
        <button class="btn" id="s3-btn-wfo">📈 Walk-Forward</button>
        <button class="btn" id="s3-btn-mc">🎲 Monte Carlo</button>
        <button class="btn" id="s3-btn-portfolio">🏆 Portfolio Compare</button>
        <button class="btn primary" id="s3-btn-export">📄 Export Report</button>
      </div>
      <div id="s3-content" style="display:none;"></div>
      <div id="s3-result" style="margin-top:12px;"></div>
    `;

    const main =
      document.querySelector("#view-backtest") ||
      document.querySelector(".main") ||
      document.body;
    main.appendChild(panel);

    document.getElementById("s3-btn-conditions").onclick = showConditionBuilder;
    document.getElementById("s3-btn-wfo").onclick = showWalkForward;
    document.getElementById("s3-btn-mc").onclick = showMonteCarlo;
    document.getElementById("s3-btn-portfolio").onclick = showPortfolio;
    document.getElementById("s3-btn-export").onclick = doExport;

    return panel;
  }

  function showContent(html) {
    const box = document.getElementById("s3-content");
    box.style.display = "block";
    box.innerHTML = html;
  }

  function showResult(html) {
    document.getElementById("s3-result").innerHTML = html;
  }

  // ----------------------------------------------------------
  // Condition Builder UI
  // ----------------------------------------------------------
  let _presets = null;

  async function showConditionBuilder() {
    if (!_presets) {
      const data = await getPresets();
      _presets = data;
    }
    const presetKeys = Object.keys(_presets.presets || {});
    const opts = presetKeys.map((k) => `<option value="${k}">${k}</option>`).join("");

    showContent(`
      <h4 style="margin-bottom:8px;">Condition Builder</h4>
      <div class="form-group">
        <label>Preset</label>
        <select id="s3-preset" class="form-control">${opts}</select>
      </div>
      <div class="form-group">
        <label>Rules JSON (edit manual)</label>
        <textarea id="s3-rules-json" rows="8" class="form-control" style="font-family:monospace;font-size:11px;"></textarea>
      </div>
      <button class="btn primary" id="s3-preview-cond">Preview Signals</button>
    `);

    const applyPreset = () => {
      const key = document.getElementById("s3-preset").value;
      const rules = _presets.presets[key];
      document.getElementById("s3-rules-json").value = JSON.stringify(rules, null, 2);
    };
    document.getElementById("s3-preset").onchange = applyPreset;
    applyPreset();

    document.getElementById("s3-preview-cond").onclick = async () => {
      try {
        const rules = JSON.parse(document.getElementById("s3-rules-json").value);
        const res = await previewConditions(rules);
        if (!res.success) {
          showResult(`<span style="color:var(--red)">${res.error}</span>`);
          return;
        }
        showResult(`
          <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);">
            <div class="kpi-card"><div class="label">BARS</div><div class="val">${res.bars}</div></div>
            <div class="kpi-card"><div class="label">BUY SIGNALS</div><div class="val" style="color:var(--green)">${res.buy_signals}</div></div>
            <div class="kpi-card"><div class="label">SELL SIGNALS</div><div class="val" style="color:var(--red)">${res.sell_signals}</div></div>
          </div>
          <p style="font-size:11px;color:var(--text-muted);margin-top:8px;">
            Simpan rules ini ke <code>window.Stage3.currentRules</code> untuk dipakai di backtest override.
          </p>
        `);
        window.Stage3.currentRules = rules;
      } catch (e) {
        showResult(`<span style="color:var(--red)">JSON error: ${e.message}</span>`);
      }
    };
  }

  // ----------------------------------------------------------
  // Walk-Forward UI
  // ----------------------------------------------------------
  function showWalkForward() {
    showContent(`
      <h4>Walk-Forward Optimization</h4>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
        <div class="form-group"><label>IS Months</label><input id="s3-is-m" type="number" value="6" class="form-control"></div>
        <div class="form-group"><label>OOS Months</label><input id="s3-oos-m" type="number" value="2" class="form-control"></div>
        <div class="form-group"><label>Step Months</label><input id="s3-step-m" type="number" value="2" class="form-control"></div>
      </div>
      <p style="font-size:11px;color:var(--text-muted);">Param space default: TP [30..80], SL [20..50], Lot [0.05..0.15]</p>
      <button class="btn primary" id="s3-run-wfo">▶ Run Walk-Forward</button>
      <div id="s3-wfo-prog" style="margin-top:8px;font-size:12px;color:var(--gold);"></div>
    `);

    document.getElementById("s3-run-wfo").onclick = async () => {
      const code =
        window.currentMqlCode ||
        document.getElementById("mqlCode")?.value ||
        document.getElementById("eaCode")?.value ||
        "";
      if (!code.trim()) {
        alert("Kode EA kosong");
        return;
      }

      const progEl = document.getElementById("s3-wfo-prog");
      progEl.textContent = "Starting…";

      try {
        const start = await startWalkForward({
          code,
          symbol: document.getElementById("symbol")?.value || "XAUUSD",
          start_date: document.getElementById("startDate")?.value || "2024-01-01",
          end_date: document.getElementById("endDate")?.value || "2024-12-31",
          balance: parseFloat(document.getElementById("balance")?.value || 10000),
          is_months: parseInt(document.getElementById("s3-is-m").value || 6),
          oos_months: parseInt(document.getElementById("s3-oos-m").value || 2),
          step_months: parseInt(document.getElementById("s3-step-m").value || 2),
          editable: window.Stage2?.collectEditableFromForm?.() || {},
        });

        if (!start.success) {
          progEl.textContent = start.error;
          return;
        }

        const final = await pollJob(start.job_id, (p, st) => {
          progEl.textContent = `Progress: ${p}% (${st})`;
        });

        const r = final.result || {};
        const agg = r.aggregate || {};
        const windows = r.windows || [];

        let rows = windows
          .map(
            (w, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${w.window?.oos_start} → ${w.window?.oos_end}</td>
            <td>${JSON.stringify(w.best_params)}</td>
            <td>${w.is_metrics?.net_profit}</td>
            <td>${w.oos_metrics?.net_profit}</td>
            <td>${w.oos_metrics?.max_drawdown_pct ?? "—"}</td>
          </tr>`
          )
          .join("");

        showResult(`
          <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);">
            <div class="kpi-card"><div class="label">OOS NET</div><div class="val">$${agg.oos_net_profit ?? 0}</div></div>
            <div class="kpi-card"><div class="label">IS NET</div><div class="val">$${agg.is_net_profit ?? 0}</div></div>
            <div class="kpi-card"><div class="label">EFFICIENCY</div><div class="val">${agg.efficiency_ratio ?? 0}</div></div>
            <div class="kpi-card"><div class="label">VERDICT</div><div class="val" style="font-size:14px">${agg.verdict ?? "—"}</div></div>
          </div>
          <table style="width:100%;margin-top:12px;font-size:11px;">
            <thead><tr><th>#</th><th>OOS Window</th><th>Best Params</th><th>IS Net</th><th>OOS Net</th><th>OOS DD%</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        `);
        progEl.textContent = "Done.";
      } catch (e) {
        progEl.textContent = "Error: " + e.message;
      }
    };
  }

  // ----------------------------------------------------------
  // Monte Carlo UI
  // ----------------------------------------------------------
  function showMonteCarlo() {
    showContent(`
      <h4>Monte Carlo Robustness</h4>
      <p style="font-size:11px;color:var(--text-muted);">
        Memakai daftar profit trade dari backtest terakhir (window.Stage3.lastTrades).
        Jika kosong, paste JSON array of numbers.
      </p>
      <div class="form-group">
        <label>Trade Profits (JSON array)</label>
        <textarea id="s3-mc-profits" rows="4" class="form-control" style="font-family:monospace;font-size:11px;"
          placeholder="[12.5, -8.2, 30.1, ...]"></textarea>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div class="form-group"><label>Simulations</label><input id="s3-mc-n" type="number" value="1000" class="form-control"></div>
        <div class="form-group"><label>Method</label>
          <select id="s3-mc-method" class="form-control">
            <option value="shuffle">Shuffle</option>
            <option value="bootstrap">Bootstrap</option>
          </select>
        </div>
      </div>
      <button class="btn primary" id="s3-run-mc">▶ Run Monte Carlo</button>
    `);

    // Pre-fill dari last trades jika ada
    const last = window.Stage3?.lastTrades;
    if (last && last.length) {
      const profits = last.map((t) => t.profit ?? t._profit ?? 0);
      document.getElementById("s3-mc-profits").value = JSON.stringify(profits);
    }

    document.getElementById("s3-run-mc").onclick = async () => {
      try {
        let profits = JSON.parse(document.getElementById("s3-mc-profits").value || "[]");
        const res = await startMonteCarlo({
          trade_profits: profits,
          n_simulations: parseInt(document.getElementById("s3-mc-n").value || 1000),
          method: document.getElementById("s3-mc-method").value,
          balance: parseFloat(document.getElementById("balance")?.value || 10000),
        });
        if (!res.success) {
          showResult(`<span style="color:var(--red)">${res.error}</span>`);
          return;
        }
        const np = res.net_profit || {};
        const dd = res.max_drawdown_pct || {};
        showResult(`
          <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);">
            <div class="kpi-card"><div class="label">P(PROFIT)</div><div class="val">${res.prob_profit}%</div></div>
            <div class="kpi-card"><div class="label">P(DD≥20%)</div><div class="val">${res.prob_ruin_20pct}%</div></div>
            <div class="kpi-card"><div class="label">NP MEDIAN</div><div class="val">$${np.median}</div></div>
            <div class="kpi-card"><div class="label">VERDICT</div><div class="val" style="font-size:14px">${res.verdict}</div></div>
          </div>
          <p style="font-size:11px;margin-top:8px;color:var(--text-muted);">
            Net Profit 5–95%: $${np.p5} … $${np.p95} · MaxDD p95: ${dd.p95}% · Worst DD: ${dd.worst}%
          </p>
        `);
      } catch (e) {
        showResult(`<span style="color:var(--red)">${e.message}</span>`);
      }
    };
  }

  // ----------------------------------------------------------
  // Portfolio (simple single-form for demo)
  // ----------------------------------------------------------
  function showPortfolio() {
    showContent(`
      <h4>Portfolio / Multi-Symbol Compare</h4>
      <p style="font-size:11px;color:var(--text-muted);">
        Jalankan EA yang sama di beberapa symbol. Pisahkan symbol dengan koma.
      </p>
      <div class="form-group">
        <label>Symbols</label>
        <input id="s3-port-symbols" class="form-control" value="XAUUSD,EURUSD,GBPUSD">
      </div>
      <button class="btn primary" id="s3-run-port">▶ Compare</button>
      <div id="s3-port-prog" style="margin-top:8px;font-size:12px;color:var(--gold);"></div>
    `);

    document.getElementById("s3-run-port").onclick = async () => {
      const code =
        window.currentMqlCode ||
        document.getElementById("mqlCode")?.value ||
        document.getElementById("eaCode")?.value ||
        "";
      if (!code.trim()) {
        alert("Kode EA kosong");
        return;
      }
      const symbols = document
        .getElementById("s3-port-symbols")
        .value.split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const base = {
        mql5_code: code,
        start_date: document.getElementById("startDate")?.value || "2024-01-01",
        end_date: document.getElementById("endDate")?.value || "2024-12-31",
        balance: parseFloat(document.getElementById("balance")?.value || 10000),
        lot: 0.1,
      };

      const items = symbols.map((sym) => ({
        id: sym,
        label: sym,
        params: { ...base, symbol: sym },
      }));

      const progEl = document.getElementById("s3-port-prog");
      progEl.textContent = "Starting…";

      try {
        const start = await startPortfolio(items);
        if (!start.success) {
          progEl.textContent = start.error;
          return;
        }
        const final = await pollJob(start.job_id, (p, st) => {
          progEl.textContent = `Progress: ${p}% (${st})`;
        });
        const r = final.result || {};
        const board = r.leaderboard || [];
        const sum = r.summary || {};

        const rows = board
          .map(
            (b, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${b.label}</td>
            <td>$${b.metrics?.net_profit ?? 0}</td>
            <td>${b.metrics?.profit_factor ?? 0}</td>
            <td>${b.metrics?.max_drawdown_pct ?? 0}%</td>
            <td>${b.metrics?.scientific_score ?? 0}</td>
            <td>${b.metrics?.status_label ?? ""}</td>
          </tr>`
          )
          .join("");

        showResult(`
          <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);">
            <div class="kpi-card"><div class="label">PORTFOLIO NET</div><div class="val">$${sum.portfolio_net_profit ?? 0}</div></div>
            <div class="kpi-card"><div class="label">AVG SCORE</div><div class="val">${sum.avg_scientific_score ?? 0}</div></div>
            <div class="kpi-card"><div class="label">BEST</div><div class="val" style="font-size:13px">${sum.best ?? "—"}</div></div>
          </div>
          <table style="width:100%;margin-top:12px;font-size:11px;">
            <thead><tr><th>#</th><th>Symbol</th><th>Net</th><th>PF</th><th>DD%</th><th>Score</th><th>Status</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        `);
        progEl.textContent = "Done.";
      } catch (e) {
        progEl.textContent = "Error: " + e.message;
      }
    };
  }

  // ----------------------------------------------------------
  // Export
  // ----------------------------------------------------------
  async function doExport() {
    const result = window.Stage3?.lastReport || window.lastBacktestResult || {};
    if (!result || !Object.keys(result).length) {
      alert("Belum ada hasil backtest untuk di-export. Jalankan backtest dulu.");
      return;
    }
    try {
      const res = await exportReport(result, "export-" + Date.now(), false);
      if (!res.success) {
        alert(res.error || "Export gagal");
        return;
      }
      // Buka HTML di tab baru
      const w = window.open("", "_blank");
      if (w && res.html) {
        w.document.write(res.html);
        w.document.close();
      } else {
        alert("Report disimpan: " + (res.path || "OK"));
      }
    } catch (e) {
      alert(e.message);
    }
  }

  // ----------------------------------------------------------
  // Hook: simpan last report/trades dari Stage2 updateKPI
  // ----------------------------------------------------------
  function hookStage2() {
    if (!window.Stage2) return;
    const orig = window.Stage2.updateKPIFromReport;
    if (typeof orig === "function") {
      window.Stage2.updateKPIFromReport = function (report) {
        orig(report);
        window.Stage3.lastReport = report;
        if (report && report.trades) {
          window.Stage3.lastTrades = report.trades;
        }
      };
    }
  }

  // Init
  function init() {
    ensurePanel();
    hookStage2();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.Stage3 = {
    getPresets,
    previewConditions,
    startWalkForward,
    startMonteCarlo,
    startPortfolio,
    exportReport,
    pollJob,
    currentRules: null,
    lastReport: null,
    lastTrades: null,
  };
})(window);
