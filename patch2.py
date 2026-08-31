path = "templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = []

# --- 1. HTML: canvas lebih besar, tambah tabel trade history, equity chart diperkecil ---
replacements.append((
'''        <canvas id="simCandleCanvas" width="1200" height="360" style="width:100%; background:#070c14; border:1px solid var(--border); border-radius:6px;"></canvas>

        <h3 style="margin-top:18px;">📈 Equity Curve Playback</h3>
        <canvas id="simEquityCanvas" height="120"></canvas>
      </div>
    </div>''',
'''        <canvas id="simCandleCanvas" width="1200" height="360" style="width:100%; height:520px; background:#070c14; border:1px solid var(--border); border-radius:6px; display:block;"></canvas>

        <div class="card" style="margin-top:14px; padding:12px 14px;">
          <h3 style="margin:0 0 8px 0; font-size:13px;">📜 Riwayat Trading (Simulasi Berjalan)</h3>
          <div id="simTradeHistoryWrap" style="max-height:220px; overflow-y:auto; border:1px solid var(--border); border-radius:6px;">
            <table style="width:100%; border-collapse:collapse; font-family:var(--font-mono); font-size:11px;">
              <thead style="position:sticky; top:0; background:#0d1420;">
                <tr style="text-align:left; color:var(--text-muted);">
                  <th style="padding:6px 8px;">#</th>
                  <th style="padding:6px 8px;">Arah</th>
                  <th style="padding:6px 8px;">Buka</th>
                  <th style="padding:6px 8px;">Entry</th>
                  <th style="padding:6px 8px;">Tutup</th>
                  <th style="padding:6px 8px;">Exit</th>
                  <th style="padding:6px 8px;">Profit</th>
                </tr>
              </thead>
              <tbody id="simTradeHistoryBody">
                <tr><td colspan="7" style="padding:10px 8px; color:var(--text-muted);">Belum ada trade.</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <h3 style="margin-top:18px; font-size:13px;">📈 Equity Curve Playback</h3>
        <div style="position:relative; height:110px; width:100%;">
          <canvas id="simEquityCanvas"></canvas>
        </div>
      </div>
    </div>'''
))

# --- 2. Chart.js equity: matikan maintainAspectRatio biar tinggi 110px ke-lock ---
replacements.append((
    '        responsive: true,\n        animation: false,',
    '        responsive: true,\n        maintainAspectRatio: false,\n        animation: false,'
))

# --- 3. Fix bug floating profit multi-posisi + return openTrades ---
replacements.append((
'''    const trades = normalizeTrades(simData.trades || []);
    if (!trades.length) {
      // Fallback: backend tidak mengirim daftar trade granular, pakai nilai bawaan.
      const balanceFallback = toNumber(f.balance, initialBalance);
      const equityFallback = toNumber(f.equity, initialBalance);
      return { balance: balanceFallback, equity: equityFallback, profit: equityFallback - initialBalance };
    }

    const curTime = new Date(f.t).getTime();
    let realizedProfit = 0;
    let openTrade = null;

    trades.forEach(t => {
      const openTime = new Date(t._openTime).getTime();
      const closeTime = new Date(t._closeTime).getTime();
      const isClosed = !isNaN(closeTime) && closeTime <= curTime;
      const isOpenNow = !isNaN(openTime) && openTime <= curTime && !isClosed;

      if (isClosed) realizedProfit += t._profit;
      else if (isOpenNow) openTrade = t;
    });

    const balance = initialBalance + realizedProfit;
    // Floating profit dari trade yang sedang berjalan (pakai field dari backend jika tersedia)
    const floating = openTrade
      ? toNumber(openTrade.floating_profit ?? openTrade.unrealized_profit ?? openTrade._profit, 0)
      : 0;
    const equity = balance + floating;
    const profit = equity - initialBalance; // total P&L simulasi berjalan (realized + floating)

    return { balance, equity, profit };
  }''',
'''    const trades = normalizeTrades(simData.trades || []);
    if (!trades.length) {
      // Fallback: backend tidak mengirim daftar trade granular, pakai nilai bawaan.
      const balanceFallback = toNumber(f.balance, initialBalance);
      const equityFallback = toNumber(f.equity, initialBalance);
      return { balance: balanceFallback, equity: equityFallback, profit: equityFallback - initialBalance, openTrades: [] };
    }

    const curTime = new Date(f.t).getTime();
    let realizedProfit = 0;
    let openTrades = [];

    trades.forEach(t => {
      const openTime = new Date(t._openTime).getTime();
      const closeTime = new Date(t._closeTime).getTime();
      const isClosed = !isNaN(closeTime) && closeTime <= curTime;
      const isOpenNow = !isNaN(openTime) && openTime <= curTime && !isClosed;

      if (isClosed) realizedProfit += t._profit;
      // FIX: dulu cuma nyimpen 1 trade terakhir (openTrade = t), posisi lain yang
      // open bersamaan jadi tidak ikut dihitung. Sekarang akumulasi SEMUA posisi terbuka.
      else if (isOpenNow) openTrades.push(t);
    });

    const balance = initialBalance + realizedProfit;
    // Floating profit = total dari SEMUA trade yang sedang berjalan, bukan cuma satu
    const floating = openTrades.reduce(
      (sum, t) => sum + toNumber(t.floating_profit ?? t.unrealized_profit ?? t._profit, 0),
      0
    );
    const equity = balance + floating;
    const profit = equity - initialBalance; // total P&L simulasi berjalan (realized + floating)

    return { balance, equity, profit, openTrades };
  }'''
))

# --- 4. Sisipkan fungsi resize responsif sebelum drawCandles ---
replacements.append((
    '  function drawCandles(slice, trades = []) {',
'''  function resizeSimCandleCanvas() {
    const canvas = document.getElementById('simCandleCanvas');
    if (!canvas) return;
    const displayWidth = Math.round(canvas.clientWidth || canvas.parentElement?.clientWidth || 1200);
    const displayHeight = Math.max(420, Math.min(620, Math.round(displayWidth * 0.36)));
    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth;
      canvas.height = displayHeight;
    }
  }

  window.addEventListener('resize', () => {
    if (!simData) return;
    resizeSimCandleCanvas();
    renderSimFrame(simFrameIdx);
  });

  function drawCandles(slice, trades = []) {'''
))

# --- 5. Tambah marker EXIT (close) di drawCandles, di samping marker ENTRY yang sudah ada ---
replacements.append((
'''    // --- Marker sinyal BUY/SELL di titik candle open trade ---
    if (trades && trades.length) {
      const SIZE = 6;
      trades.forEach(t => {
        const openTime = new Date(t._openTime).getTime();
        if (isNaN(openTime)) return;
        const mIdx = slice.findIndex(c => new Date(c.t).getTime() === openTime);
        if (mIdx === -1) return;
        const c = slice[mIdx];
        const x = MARGIN_LEFT + mIdx * cw + cw / 2;
        const isBuy = (t._direction || '').toUpperCase().includes('BUY');
        ctx.fillStyle = isBuy ? '#10b981' : '#f43f5e';
        ctx.beginPath();
        if (isBuy) {
          const y = yOf(c.l) + SIZE + 4;
          ctx.moveTo(x, y - SIZE);
          ctx.lineTo(x - SIZE, y + SIZE);
          ctx.lineTo(x + SIZE, y + SIZE);
        } else {
          const y = yOf(c.h) - SIZE - 4;
          ctx.moveTo(x, y + SIZE);
          ctx.lineTo(x - SIZE, y - SIZE);
          ctx.lineTo(x + SIZE, y - SIZE);
        }
        ctx.closePath();
        ctx.fill();
      });
    }''',
'''    // --- Marker sinyal BUY/SELL (entry) + marker close (exit) per trade ---
    if (trades && trades.length) {
      const SIZE = 6;
      trades.forEach(t => {
        // Marker ENTRY di candle waktu trade dibuka
        const openTime = new Date(t._openTime).getTime();
        if (!isNaN(openTime)) {
          const oIdx = slice.findIndex(c => new Date(c.t).getTime() === openTime);
          if (oIdx !== -1) {
            const c = slice[oIdx];
            const x = MARGIN_LEFT + oIdx * cw + cw / 2;
            const isBuy = (t._direction || '').toUpperCase().includes('BUY');
            ctx.fillStyle = isBuy ? '#10b981' : '#f43f5e';
            ctx.beginPath();
            if (isBuy) {
              const y = yOf(c.l) + SIZE + 4;
              ctx.moveTo(x, y - SIZE);
              ctx.lineTo(x - SIZE, y + SIZE);
              ctx.lineTo(x + SIZE, y + SIZE);
            } else {
              const y = yOf(c.h) - SIZE - 4;
              ctx.moveTo(x, y + SIZE);
              ctx.lineTo(x - SIZE, y - SIZE);
              ctx.lineTo(x + SIZE, y - SIZE);
            }
            ctx.closePath();
            ctx.fill();
          }
        }

        // Marker EXIT di candle waktu trade ditutup - lingkaran, warna sesuai untung/rugi
        // posisi Y pakai harga close ASLI dari trade (t._close), bukan tebakan, supaya valid
        const closeTime = new Date(t._closeTime).getTime();
        if (!isNaN(closeTime)) {
          const eIdx = slice.findIndex(c => new Date(c.t).getTime() === closeTime);
          if (eIdx !== -1) {
            const c = slice[eIdx];
            const x = MARGIN_LEFT + eIdx * cw + cw / 2;
            const y = yOf(t._close || c.c);
            ctx.strokeStyle = t._profit >= 0 ? '#10b981' : '#f43f5e';
            ctx.fillStyle = '#070c14';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, SIZE * 0.7, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
          }
        }
      });
    }'''
))

# --- 6. renderSimFrame: panggil resize, isi tabel riwayat trade ---
replacements.append((
'''  function renderSimFrame(idx) {
    if (!simData) return;
    const frames = frames;''',  # placeholder never matches, safety no-op
    ''
))
# (baris di atas sengaja tidak dipakai; replacement asli renderSimFrame ada di bawah)

replacements[-1] = ((
'''  function renderSimFrame(idx) {
    if (!simData) return;
    const frames = simData.frames;
    const f = frames[idx];

    const { balance, profit } = computeSimBalanceEquity(idx);

    document.getElementById('simFrameLabel').innerText = `${idx + 1} / ${frames.length}`;
    document.getElementById('simSeek').value = idx;
    document.getElementById('simBalance').innerText = money(balance);
    const profitEl = document.getElementById('simEquity');
    profitEl.innerText = (profit >= 0 ? '+' : '') + money(profit);
    profitEl.style.color = profit >= 0 ? '#10b981' : '#f43f5e';
    document.getElementById('simTrades').innerText = f.trades_total;
    document.getElementById('simDD').innerText = f.drawdown + '%';

    const badge = document.getElementById('simStatusBadge');
    if (f.position === 'BUY') { badge.className = 'badge green'; badge.innerText = 'LONG'; }
    else if (f.position === 'SELL') { badge.className = 'badge red'; badge.innerText = 'SHORT'; }
    else { badge.className = 'badge yellow'; badge.innerText = 'FLAT'; }

    const WINDOW = 100;
    const start = Math.max(0, idx - WINDOW);
    const tradesForMarkers = normalizeTrades(simData.trades || []);
    drawCandles(frames.slice(start, idx + 1), tradesForMarkers);

    const eqSlice = frames.slice(0, idx + 1);
    simEquityChart.data.labels = eqSlice.map(x => x.t);
    simEquityChart.data.datasets[0].data = eqSlice.map((x, i) => computeSimBalanceEquity(i).equity);
    simEquityChart.update('none');
  }''',
'''  let simLastHistoryCount = -1;

  function updateSimTradeHistory(idx) {
    const f = simData.frames[idx];
    const curTime = new Date(f.t).getTime();
    const trades = normalizeTrades(simData.trades || []);

    const visible = trades.filter(t => {
      const ot = new Date(t._openTime).getTime();
      return !isNaN(ot) && ot <= curTime;
    });

    // Jangan render ulang tabel tiap frame kalau jumlah trade belum berubah (jaga performa playback)
    if (visible.length === simLastHistoryCount) return;
    simLastHistoryCount = visible.length;

    const body = document.getElementById('simTradeHistoryBody');
    if (!body) return;

    if (!visible.length) {
      body.innerHTML = '<tr><td colspan="7" style="padding:10px 8px; color:var(--text-muted);">Belum ada trade.</td></tr>';
      return;
    }

    body.innerHTML = visible.slice().reverse().map(t => {
      const closeTime = new Date(t._closeTime).getTime();
      const isClosed = !isNaN(closeTime) && closeTime <= curTime;
      const dirColor = (t._direction || '').toUpperCase().includes('BUY') ? '#10b981' : '#f43f5e';
      const profitVal = isClosed ? t._profit : toNumber(t.floating_profit ?? t.unrealized_profit ?? t._profit, 0);
      const profitColor = profitVal >= 0 ? '#10b981' : '#f43f5e';
      return `<tr style="border-top:1px solid var(--border);">
        <td style="padding:5px 8px;">${t._index}</td>
        <td style="padding:5px 8px; color:${dirColor}; font-weight:700;">${t._direction || '-'}</td>
        <td style="padding:5px 8px;">${formatCandleTime(t._openTime)}</td>
        <td style="padding:5px 8px;">${price(t._entry)}</td>
        <td style="padding:5px 8px;">${isClosed ? formatCandleTime(t._closeTime) : 'OPEN'}</td>
        <td style="padding:5px 8px;">${isClosed ? price(t._close) : '-'}</td>
        <td style="padding:5px 8px; color:${profitColor}; font-weight:700;">${(profitVal >= 0 ? '+' : '') + money(profitVal)}</td>
      </tr>`;
    }).join('');
  }

  function renderSimFrame(idx) {
    if (!simData) return;
    resizeSimCandleCanvas();
    const frames = simData.frames;
    const f = frames[idx];

    const { balance, profit } = computeSimBalanceEquity(idx);

    document.getElementById('simFrameLabel').innerText = `${idx + 1} / ${frames.length}`;
    document.getElementById('simSeek').value = idx;
    document.getElementById('simBalance').innerText = money(balance);
    const profitEl = document.getElementById('simEquity');
    profitEl.innerText = (profit >= 0 ? '+' : '') + money(profit);
    profitEl.style.color = profit >= 0 ? '#10b981' : '#f43f5e';
    document.getElementById('simTrades').innerText = f.trades_total;
    document.getElementById('simDD').innerText = f.drawdown + '%';

    const badge = document.getElementById('simStatusBadge');
    if (f.position === 'BUY') { badge.className = 'badge green'; badge.innerText = 'LONG'; }
    else if (f.position === 'SELL') { badge.className = 'badge red'; badge.innerText = 'SHORT'; }
    else { badge.className = 'badge yellow'; badge.innerText = 'FLAT'; }

    const WINDOW = 100;
    const start = Math.max(0, idx - WINDOW);
    const tradesForMarkers = normalizeTrades(simData.trades || []);
    drawCandles(frames.slice(start, idx + 1), tradesForMarkers);

    updateSimTradeHistory(idx);

    const eqSlice = frames.slice(0, idx + 1);
    simEquityChart.data.labels = eqSlice.map(x => x.t);
    simEquityChart.data.datasets[0].data = eqSlice.map((x, i) => computeSimBalanceEquity(i).equity);
    simEquityChart.update('none');
  }'''
))

ok = True
for i, (old, new) in enumerate(replacements, 1):
    if not old:
        continue
    if old not in content:
        print(f"[GAGAL] pola #{i} tidak ditemukan.")
        ok = False

if ok:
    for old, new in replacements:
        if not old:
            continue
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] index.html berhasil di-patch.")
else:
    print("[BATAL] ada pola tidak cocok - kemungkinan file sudah beda dari yang diasumsikan (misal patch sebelumnya belum ke-apply). Cek manual dulu.")
