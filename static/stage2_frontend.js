/**
 * stage2_frontend.js
 * Pintarin Laboratorium EA – Stage 2 UI helpers
 *
 * Fitur:
 *  1. Parse EA → tampilkan panel parameter yang bisa diedit
 *  2. Enrich KPI cards (Scientific Score, Win Rate, Expectancy, Jackpot Risk)
 *  3. Helper untuk memanggil endpoint Stage 2
 *
 * Cara pakai di index.html (di akhir <body>):
 *   <script src="/static/stage2_frontend.js"></script>
 *   atau paste langsung isi file ini.
 */

(function (window) {
  "use strict";

  // ----------------------------------------------------------
  // STATE
  // ----------------------------------------------------------
  let lastTradingLogic = null;
  let lastEditable = null;

  // ----------------------------------------------------------
  // API CALLS
  // ----------------------------------------------------------

  async function parseEA(code, fileName = "Expert Advisor") {
    const res = await fetch("/api/parse-ea", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, mql5_code: code, file_name: fileName }),
    });
    return res.json();
  }

  async function explainAndParse(code, fileName = "Expert Advisor") {
    const res = await fetch("/api/explain-and-parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, mql5_code: code, file_name: fileName }),
    });
    return res.json();
  }

  async function runBacktestWithParams(payload) {
    const res = await fetch("/api/run-backtest-with-params", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.json();
  }

  // ----------------------------------------------------------
  // RENDER PARAMETER PANEL
  // ----------------------------------------------------------

  function ensureParamPanel() {
    let panel = document.getElementById("stage2-param-panel");
    if (panel) return panel;

    // Cari container control card
    const controlCard =
      document.querySelector("#view-backtest .card") ||
      document.querySelector(".grid-control .card") ||
      document.getElementById("view-backtest");

    panel = document.createElement("div");
    panel.id = "stage2-param-panel";
    panel.className = "card";
    panel.style.display = "none";
    panel.style.marginTop = "14px";
    panel.innerHTML = `
      <h3 style="display:flex;align-items:center;gap:8px;">
        🎛️ Parameter dari AI
        <span id="stage2-strategy-badge" style="
          font-size:10px;padding:2px 8px;border-radius:999px;
          background:rgba(217,167,92,0.2);color:var(--gold);font-weight:700;
        ">—</span>
      </h3>
      <p id="stage2-summary-desc" style="color:var(--text-muted);font-size:11px;margin-bottom:12px;"></p>

      <div class="form-row" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div class="form-group">
          <label>Take Profit (pips)</label>
          <input type="number" id="s2-tp" step="0.1" class="form-control">
        </div>
        <div class="form-group">
          <label>Stop Loss (pips)</label>
          <input type="number" id="s2-sl" step="0.1" class="form-control">
        </div>
        <div class="form-group">
          <label>Trailing Stop</label>
          <input type="number" id="s2-trailing" step="0.1" class="form-control">
        </div>
        <div class="form-group">
          <label>Break Even</label>
          <input type="number" id="s2-breakeven" step="0.1" class="form-control">
        </div>
        <div class="form-group">
          <label>Base Lot</label>
          <input type="number" id="s2-base-lot" step="0.01" class="form-control">
        </div>
        <div class="form-group">
          <label>Lot Multiplier</label>
          <input type="number" id="s2-multiplier" step="0.1" class="form-control">
        </div>
        <div class="form-group">
          <label>Max Positions</label>
          <input type="number" id="s2-max-pos" step="1" min="1" class="form-control">
        </div>
        <div class="form-group">
          <label>Max Lot</label>
          <input type="number" id="s2-max-lot" step="0.1" class="form-control">
        </div>
      </div>

      <div style="display:flex;align-items:center;gap:12px;margin-top:12px;">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
          <input type="checkbox" id="s2-martingale">
          <span>Martingale / Grid Mode</span>
        </label>
        <span id="stage2-indicators" style="font-size:11px;color:var(--text-muted);"></span>
      </div>

      <div style="display:flex;gap:8px;margin-top:14px;">
        <button class="btn primary" onclick="Stage2.runWithEditedParams()">▶ Run Backtest (dengan parameter ini)</button>
        <button class="btn" onclick="Stage2.hideParamPanel()">Tutup</button>
      </div>
    `;

    if (controlCard && controlCard.parentNode) {
      controlCard.parentNode.insertBefore(panel, controlCard.nextSibling);
    } else {
      document.body.appendChild(panel);
    }
    return panel;
  }

  function showParamPanel(data) {
    const panel = ensureParamPanel();
    lastTradingLogic = data.trading_logic || {};
    lastEditable = data.editable || {};

    const e = lastEditable;
    document.getElementById("s2-tp").value = e.tp ?? 50;
    document.getElementById("s2-sl").value = e.sl ?? 30;
    document.getElementById("s2-trailing").value = e.trailing ?? 0;
    document.getElementById("s2-breakeven").value = e.breakeven ?? 0;
    document.getElementById("s2-base-lot").value = e.base_lot ?? 0.1;
    document.getElementById("s2-multiplier").value = e.multiplier ?? 1.0;
    document.getElementById("s2-max-pos").value = e.max_positions ?? 1;
    document.getElementById("s2-max-lot").value = e.max_lot ?? 100;
    document.getElementById("s2-martingale").checked = !!e.martingale;

    const badge = document.getElementById("stage2-strategy-badge");
    if (badge) badge.textContent = (e.strategy_type || "—").toUpperCase();

    const summary = data.summary || {};
    const descEl = document.getElementById("stage2-summary-desc");
    if (descEl) {
      descEl.textContent =
        summary.description ||
        `Strategy: ${e.strategy_type || "?"} · Indicators: ${(summary.indicators || []).join(", ") || "—"}`;
    }

    const indEl = document.getElementById("stage2-indicators");
    if (indEl && summary.indicators) {
      indEl.textContent = "Indikator: " + summary.indicators.join(", ");
    }

    panel.style.display = "block";
  }

  function hideParamPanel() {
    const panel = document.getElementById("stage2-param-panel");
    if (panel) panel.style.display = "none";
  }

  function collectEditableFromForm() {
    return {
      strategy_type: lastEditable?.strategy_type || "ma_crossover",
      tp: parseFloat(document.getElementById("s2-tp")?.value || 50),
      sl: parseFloat(document.getElementById("s2-sl")?.value || 30),
      trailing: parseFloat(document.getElementById("s2-trailing")?.value || 0),
      breakeven: parseFloat(document.getElementById("s2-breakeven")?.value || 0),
      base_lot: parseFloat(document.getElementById("s2-base-lot")?.value || 0.1),
      multiplier: parseFloat(document.getElementById("s2-multiplier")?.value || 1),
      max_positions: parseInt(document.getElementById("s2-max-pos")?.value || 1, 10),
      max_lot: parseFloat(document.getElementById("s2-max-lot")?.value || 100),
      martingale: !!document.getElementById("s2-martingale")?.checked,
    };
  }

  // ----------------------------------------------------------
  // ENRICH KPI CARDS
  // ----------------------------------------------------------

  function ensureExtraKPI() {
    let grid = document.querySelector(".kpi-grid");
    if (!grid) return null;

    // Tambah kartu jika belum ada
    const extras = [
      { id: "kpiWinRate", label: "WIN RATE" },
      { id: "kpiExpectancy", label: "EXPECTANCY" },
      { id: "kpiScore", label: "SCIENTIFIC SCORE" },
      { id: "kpiStatus", label: "STATUS" },
    ];

    extras.forEach(({ id, label }) => {
      if (!document.getElementById(id)) {
        const card = document.createElement("div");
        card.className = "kpi-card";
        card.innerHTML = `
          <div class="label">${label}</div>
          <div class="val" id="${id}">—</div>
        `;
        grid.appendChild(card);
      }
    });

    // Risk warning banner
    if (!document.getElementById("stage2-risk-banner")) {
      const banner = document.createElement("div");
      banner.id = "stage2-risk-banner";
      banner.style.cssText = `
        display:none;margin:12px 0;padding:10px 14px;border-radius:8px;
        background:rgba(244,63,94,0.12);border:1px solid rgba(244,63,94,0.35);
        color:#fda4af;font-size:12px;font-weight:600;
      `;
      grid.parentNode.insertBefore(banner, grid.nextSibling);
    }
    return grid;
  }

  function updateKPIFromReport(report) {
    if (!report) return;
    ensureExtraKPI();

    const money = (v) => {
      const n = Number(v) || 0;
      return (n >= 0 ? "+" : "") + "$" + n.toFixed(2);
    };
    const num = (v, d = 2) => (Number(v) || 0).toFixed(d);

    // Existing
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    if (report.net_profit !== undefined) set("kpiProfit", money(report.net_profit));
    if (report.profit_factor !== undefined) set("kpiPF", num(report.profit_factor));
    if (report.sortino_ratio !== undefined) set("kpiSortino", num(report.sortino_ratio));
    if (report.max_drawdown_pct !== undefined)
      set("kpiDD", num(report.max_drawdown_pct) + "%");

    // New
    if (report.win_rate !== undefined) set("kpiWinRate", num(report.win_rate) + "%");
    if (report.expectancy !== undefined) set("kpiExpectancy", money(report.expectancy));

    const score = report.scientific_score;
    if (score !== undefined) {
      const el = document.getElementById("kpiScore");
      if (el) {
        el.innerText = num(score, 1);
        el.style.color =
          score >= 80 ? "var(--green)" : score >= 60 ? "var(--yellow)" : "var(--red)";
      }
    }

    const status = report.status_label || "—";
    const statusEl = document.getElementById("kpiStatus");
    if (statusEl) {
      const emoji = report.status_emoji || "";
      statusEl.innerText = `${emoji} ${status}`;
      statusEl.style.color = report.status_color || "var(--gold)";
      statusEl.style.fontSize = "13px";
    }

    // Risk banner
    const banner = document.getElementById("stage2-risk-banner");
    if (banner) {
      if (report.is_jackpot_dependent || report.risk_warning) {
        banner.style.display = "block";
        banner.innerText =
          "⚠️ " +
          (report.risk_warning ||
            `Jackpot Dependent — Top-5 trade = ${num(report.top5_concentration_pct || 0)}% profit`);
      } else {
        banner.style.display = "none";
      }
    }
  }

  // ----------------------------------------------------------
  // ACTIONS
  // ----------------------------------------------------------

  async function analyzeCurrentEA() {
    // Ambil kode dari textarea atau state global
    const codeEl =
      document.getElementById("mql5CodeInput") ||
      document.getElementById("mqlCode") ||
      document.getElementById("eaCode") ||
      document.querySelector("textarea");
    const code = (window.currentMqlCode || codeEl?.value || "").trim();

    if (!code) {
      alert("Kode EA kosong. Upload atau paste dulu.");
      return;
    }

    const btn = document.getElementById("btn-stage2-parse");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "⏳ Analyzing…";
    }

    try {
      const data = await explainAndParse(code);
      if (!data.success) {
        alert(data.error || data.explanation || "Gagal menganalisis EA");
        return;
      }

      // Tampilkan penjelasan teks jika ada container
      const explBox =
        document.getElementById("aiExplanation") ||
        document.getElementById("explanationResult");
      if (explBox && data.explanation) {
        explBox.innerText = data.explanation;
        explBox.style.whiteSpace = "pre-wrap";
      }

      if (data.editable && Object.keys(data.editable).length) {
        showParamPanel(data);
      }
    } catch (err) {
      console.error(err);
      alert("Error: " + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "🤖 AI Parse & Kalibrasi";
      }
    }
  }

  async function runWithEditedParams() {
    const code =
      window.currentMqlCode ||
      document.getElementById("mql5CodeInput")?.value ||
      document.getElementById("mqlCode")?.value ||
      document.getElementById("eaCode")?.value ||
      document.querySelector("textarea")?.value ||
      "";

    if (!code.trim()) {
      alert("Kode EA kosong. Upload atau paste dulu.");
      return;
    }

    const editable = collectEditableFromForm();
    const balanceEl =
      document.getElementById("balance") || document.getElementById("initialBalance");
    const symbolEl = document.getElementById("symbol");

    const payload = {
      code,
      mql5_code: code,
      editable,
      balance: parseFloat(balanceEl?.value || 10000),
      symbol: symbolEl?.value || "XAUUSD",
      start_date: document.getElementById("startDate")?.value || "2024-01-01",
      end_date: document.getElementById("endDate")?.value || "2024-12-31",
      ea_name: window.currentEaName || "EA_MQL5",
    };

    const runBtn = document.querySelector("#stage2-param-panel .btn.primary");
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.textContent = "⏳ Running…";
    }

    try {
      const data = await runBacktestWithParams(payload);
      if (!data.success) {
        alert(data.error || "Backtest gagal");
        return;
      }

      const report = data.report || data.data || {};
      // Metrics bisa nested
      const metrics = report.metrics || report.report || report;
      updateKPIFromReport(metrics);

      // Panggil renderer yang sudah ada di index.html jika tersedia
      if (typeof renderChart === "function" && metrics.equity_curve) {
        renderChart(metrics.equity_curve);
      }
      if (typeof renderChartWithMarkers === "function") {
        renderChartWithMarkers(
          metrics.equity_curve || report.equity_curve || [],
          metrics.trades || report.trades || [],
          "Stage2"
        );
      }
      if (typeof renderTradeTable === "function") {
        renderTradeTable(metrics.trades || report.trades || []);
      }

      // Scroll ke KPI
      document.querySelector(".kpi-grid")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      console.error(err);
      alert("Error: " + err.message);
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = "▶ Run Backtest (dengan parameter ini)";
      }
    }
  }

  // ----------------------------------------------------------
  // INJECT BUTTON ke UI yang sudah ada
  // ----------------------------------------------------------

  function injectParseButton() {
    // Cari area tombol AI yang sudah ada
    const actions =
      document.querySelector(".actions") ||
      document.querySelector("#view-backtest .card") ||
      document.querySelector(".form-group");

    if (!actions || document.getElementById("btn-stage2-parse")) return;

    const btn = document.createElement("button");
    btn.id = "btn-stage2-parse";
    btn.className = "btn primary";
    btn.style.flex = "1";
    btn.style.margin = "0 0 10px 0";
    btn.style.display = "flex";
    btn.style.alignItems = "center";
    btn.style.justifyContent = "center";
    btn.style.textAlign = "center";
    btn.style.lineHeight = "1.2";
    btn.textContent = "🤖 AI Parse & Kalibrasi";
    btn.onclick = analyzeCurrentEA;

    // Letakkan di dekat tombol explain / run
    const explainBtn =
      document.getElementById("btnExplain") ||
      document.querySelector("[onclick*='explain']");
    if (explainBtn && explainBtn.parentNode) {
      explainBtn.parentNode.insertBefore(btn, explainBtn.nextSibling);
    } else {
      actions.appendChild(btn);
    }
  }

  // Auto-init saat DOM siap
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectParseButton);
  } else {
    injectParseButton();
  }

  // Export
  window.Stage2 = {
    parseEA,
    explainAndParse,
    runBacktestWithParams,
    showParamPanel,
    hideParamPanel,
    updateKPIFromReport,
    analyzeCurrentEA,
    runWithEditedParams,
    collectEditableFromForm,
  };
})(window);
