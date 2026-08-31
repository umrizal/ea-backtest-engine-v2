// ============================================================
// stage3_frontend.js
// Frontend module for Stage 3 - Backtest Engine
// ============================================================

class Stage3Frontend {
  constructor() {
    this.apiBase = '/api/stage3';
    this.results = null;
    this.initEventListeners();
  }

  initEventListeners() {
    document.addEventListener('DOMContentLoaded', () => {
      this.setupUI();
    });
  }

  setupUI() {
    const stage3Container = document.getElementById('stage3-container');
    if (stage3Container) {
      stage3Container.innerHTML = this.getTemplate();
      this.attachHandlers();
    }
  }

  getTemplate() {
    return `
      <div class="stage3-panel">
        <h2>Stage 3 - Advanced Analysis</h2>
        <div class="stage3-controls">
          <button id="btn-walkforward" class="btn btn-primary">Walk Forward Analysis</button>
          <button id="btn-portfolio-compare" class="btn btn-primary">Portfolio Compare</button>
          <button id="btn-report-export" class="btn btn-primary">Export Report</button>
        </div>
        <div id="stage3-results" class="results-container"></div>
      </div>
    `;
  }

  attachHandlers() {
    document.getElementById('btn-walkforward')?.addEventListener('click', () => this.runWalkForward());
    document.getElementById('btn-portfolio-compare')?.addEventListener('click', () => this.runPortfolioCompare());
    document.getElementById('btn-report-export')?.addEventListener('click', () => this.exportReport());
  }

  async runWalkForward() {
    try {
      const response = await fetch(`${this.apiBase}/walkforward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await response.json();
      this.displayResults('Walk Forward Results', data);
    } catch (error) {
      console.error('Walk forward error:', error);
      this.showError('Failed to run walk forward analysis');
    }
  }

  async runPortfolioCompare() {
    try {
      const response = await fetch(`${this.apiBase}/portfolio-compare`, {
        method: 'GET'
      });
      const data = await response.json();
      this.displayResults('Portfolio Comparison', data);
    } catch (error) {
      console.error('Portfolio compare error:', error);
      this.showError('Failed to run portfolio comparison');
    }
  }

  async exportReport() {
    try {
      const response = await fetch(`${this.apiBase}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stage3_report.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export error:', error);
      this.showError('Failed to export report');
    }
  }

  displayResults(title, data) {
    const container = document.getElementById('stage3-results');
    if (container) {
      container.innerHTML = `<h3>${title}</h3><pre>${JSON.stringify(data, null, 2)}</pre>`;
    }
  }

  showError(message) {
    const container = document.getElementById('stage3-results');
    if (container) {
      container.innerHTML = `<div class="error">${message}</div>`;
    }
  }
}

// Initialize Stage 3 Frontend
const stage3Frontend = new Stage3Frontend();
