/**
 * RaceDB — Benchmark.js
 * Benchmark configuration, execution, progress, results display
 */
import { apiFetch, setLoading, showToast, statusBadge, fmt, anomalyClass, anomalyIcon } from './app.js';

// ── Init ─────────────────────────────────────────────────────────────────
export function initBenchmark() {
  // Pattern selector
  document.querySelectorAll('.pattern-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.pattern-pill').forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      document.getElementById('bench-pattern').value = pill.dataset.pattern;
    });
  });

  // Select default pattern
  const defaultPill = document.querySelector('.pattern-pill[data-pattern="mixed"]');
  if (defaultPill) defaultPill.classList.add('selected');

  // Sliders
  bindSlider('bench-num-txns', 'bench-num-txns-val');
  bindSlider('bench-concurrency', 'bench-concurrency-val');

  // Run button
  document.getElementById('run-benchmark-btn').addEventListener('click', runBenchmark);

  // Reset accounts button
  document.getElementById('reset-accounts-btn')?.addEventListener('click', resetAccounts);
}

function bindSlider(sliderId, valId) {
  const slider = document.getElementById(sliderId);
  const valEl = document.getElementById(valId);
  if (!slider || !valEl) return;
  valEl.textContent = slider.value;
  slider.addEventListener('input', () => { valEl.textContent = slider.value; });
}

// ── Run Benchmark ─────────────────────────────────────────────────────────
async function runBenchmark() {
  const btn = document.getElementById('run-benchmark-btn');
  const resultsPanel = document.getElementById('benchmark-results-panel');

  const payload = {
    num_transactions: parseInt(document.getElementById('bench-num-txns').value),
    concurrency_level: parseInt(document.getElementById('bench-concurrency').value),
    pattern: document.getElementById('bench-pattern').value,
    isolation_level: document.getElementById('bench-isolation').value,
  };

  setLoading(btn, true);
  showProgress(resultsPanel, payload.num_transactions);

  try {
    const res = await apiFetch('/run-benchmark', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderBenchmarkResults(res);
    showToast(`Benchmark complete! ${res.successful}/${res.total_transactions} succeeded.`, 'success');
  } catch (err) {
    showToast(`Benchmark error: ${err.message}`, 'error');
    resultsPanel.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-title" style="color:var(--danger)">Error: ${err.message}</div>
      </div>`;
  } finally {
    setLoading(btn, false);
  }
}

function showProgress(panel, total) {
  panel.innerHTML = `
    <div class="card">
      <div class="card-title">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        Running Benchmark — ${total} transactions
      </div>
      <div class="progress-wrap">
        <div class="progress-bar animated" style="width:100%"></div>
      </div>
      <div style="font-size:0.875rem;color:var(--text-muted);margin-top:8px">
        Executing concurrent workload against MySQL InnoDB…
      </div>
    </div>`;
}

// ── Render Results ─────────────────────────────────────────────────────────
function renderBenchmarkResults(res) {
  const panel = document.getElementById('benchmark-results-panel');

  const successRate = res.total_transactions
    ? Math.round((res.successful / res.total_transactions) * 100) : 0;

  const anomaliesHTML = res.anomalies?.length
    ? res.anomalies.map(a => renderAnomalyItem(a)).join('')
    : `<div class="empty-state" style="padding:2rem">
        <div class="empty-state-title" style="color:var(--accent)">No anomalies detected</div>
        <div class="empty-state-desc">All transactions completed consistently under ${res.isolation_level}</div>
      </div>`;

  panel.innerHTML = `
    <!-- Run badge -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:1.25rem">
      <div style="font-size:1.25rem;font-weight:700;letter-spacing:-0.02em">Results</div>
      <span class="badge badge-blue" style="font-family:var(--font-mono)">Run #${res.run_id}</span>
      <span class="badge badge-success">${res.isolation_level}</span>
      <span class="badge badge-purple">${res.pattern}</span>
    </div>

    <!-- Metrics -->
    <div class="metric-grid">
      <div class="metric-card blue">
        <div class="metric-label">Total</div>
        <div class="metric-value">${fmt(res.total_transactions)}</div>
        <div class="metric-unit">transactions</div>
      </div>
      <div class="metric-card success">
        <div class="metric-label">Successful</div>
        <div class="metric-value">${fmt(res.successful)}</div>
        <div class="metric-unit">${successRate}% success rate</div>
      </div>
      <div class="metric-card danger">
        <div class="metric-label">Aborted</div>
        <div class="metric-value">${fmt(res.aborted)}</div>
        <div class="metric-unit">rollbacks + errors</div>
      </div>
      <div class="metric-card danger">
        <div class="metric-label">Deadlocks</div>
        <div class="metric-value">${fmt(res.deadlocks)}</div>
        <div class="metric-unit">MySQL 1213</div>
      </div>
      <div class="metric-card cyan">
        <div class="metric-label">Avg Latency</div>
        <div class="metric-value">${fmt(res.avg_latency_ms, 1)}</div>
        <div class="metric-unit">ms per transaction</div>
      </div>
      <div class="metric-card purple">
        <div class="metric-label">Throughput</div>
        <div class="metric-value">${fmt(res.throughput_tps, 1)}</div>
        <div class="metric-unit">transactions/sec</div>
      </div>
      <div class="metric-card warning">
        <div class="metric-label">Anomalies</div>
        <div class="metric-value">${fmt(res.anomalies_detected)}</div>
        <div class="metric-unit">detected</div>
      </div>
      <div class="metric-card blue">
        <div class="metric-label">Concurrency</div>
        <div class="metric-value">${fmt(res.concurrency_level)}</div>
        <div class="metric-unit">parallel threads</div>
      </div>
    </div>

    <!-- Success rate bar -->
    <div class="card" style="margin-bottom:1.25rem">
      <div class="card-title">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
        Success Rate Breakdown
      </div>
      <div style="margin-bottom:6px;font-size:0.8125rem;color:var(--text-muted)">${successRate}% succeeded (${res.successful} / ${res.total_transactions})</div>
      <div style="height:12px;background:var(--border);border-radius:100px;overflow:hidden;display:flex">
        <div style="width:${successRate}%;background:linear-gradient(90deg,var(--accent),#16A34A);border-radius:100px;transition:width 0.8s var(--ease)"></div>
        <div style="width:${100 - successRate}%;background:var(--danger-dim)"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.75rem;color:var(--text-muted)">
        <span style="color:var(--accent)">✓ ${res.successful} succeeded</span>
        <span style="color:var(--danger)">✗ ${res.aborted} aborted</span>
      </div>
    </div>

    <!-- Anomalies -->
    <div class="card">
      <div class="card-title">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.07 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
        Anomaly Report — ${res.anomalies_detected} detected
      </div>
      <div class="anomaly-list">${anomaliesHTML}</div>
    </div>`;
}

function renderAnomalyItem(a) {
  const cls = anomalyClass(a.type);
  const colorMap = { danger: 'var(--danger)', warning: 'var(--warning)', blue: 'var(--blue)', purple: 'var(--purple)', cyan: 'var(--cyan)' };
  const color = colorMap[cls] || 'var(--blue)';
  return `
    <div class="anomaly-item ${a.type}">
      <div class="anomaly-icon" style="color:${color}">${anomalyIcon(a.type)}</div>
      <div class="anomaly-body">
        <div class="anomaly-type">${a.type?.replace(/_/g, ' ')}</div>
        <div class="anomaly-desc">${a.description || ''}</div>
        ${a.txn_ids ? `<div class="anomaly-txns">Transactions: ${a.txn_ids}</div>` : ''}
      </div>
    </div>`;
}

// ── Reset accounts ─────────────────────────────────────────────────────────
async function resetAccounts() {
  const btn = document.getElementById('reset-accounts-btn');
  setLoading(btn, true);
  try {
    await apiFetch('/accounts/reset', { method: 'POST' });
    showToast('Account balances reset to seed values', 'success');
    // Refresh accounts display if visible
    loadAccounts();
  } catch (err) {
    showToast(`Reset failed: ${err.message}`, 'error');
  } finally {
    setLoading(btn, false);
  }
}

export async function loadAccounts() {
  const container = document.getElementById('accounts-display');
  if (!container) return;
  try {
    const data = await apiFetch('/accounts');
    if (!data.accounts?.length) { container.innerHTML = '<div class="empty-state"><div class="empty-state-title">No accounts</div></div>'; return; }
    container.innerHTML = data.accounts.map(a => `
      <div class="account-chip">
        <div class="account-id">ID #${a.account_id}</div>
        <div class="account-name">${a.owner}</div>
        <div class="account-bal">$${parseFloat(a.balance).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2})}</div>
      </div>`).join('');
  } catch {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-title" style="color:var(--text-muted)">Could not load accounts</div></div>';
  }
}
