/**
 * RaceDB — Logs.js
 * Live log viewer + benchmark history tab
 */
import { apiFetch, showToast, statusBadge, fmt } from './app.js';

let autoRefreshTimer = null;

// ── Init ──────────────────────────────────────────────────────────────────
export function initLogs() {
  document.getElementById('logs-refresh-btn').addEventListener('click', fetchLogs);
  document.getElementById('logs-filter-status').addEventListener('change', fetchLogs);
  document.getElementById('auto-refresh-toggle').addEventListener('change', toggleAutoRefresh);
  document.getElementById('logs-clear-btn')?.addEventListener('click', () => {
    document.getElementById('logs-table-body').innerHTML = '';
    document.getElementById('logs-count').textContent = '0 entries';
  });

  fetchLogs();
}

export function initHistory() {
  document.getElementById('history-refresh-btn').addEventListener('click', fetchHistory);
  fetchHistory();
}

// ── Fetch logs ────────────────────────────────────────────────────────────
async function fetchLogs() {
  const tbody = document.getElementById('logs-table-body');
  const status = document.getElementById('logs-filter-status').value;
  const limit = 100;

  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:2rem;font-family:var(--font-mono)">Loading…</td></tr>`;

  try {
    const url = status ? `/logs?status=${status}&limit=${limit}` : `/logs?limit=${limit}`;
    const data = await apiFetch(url);
    const logs = data.logs || [];

    document.getElementById('logs-count').textContent = `${logs.length} entries`;

    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:2rem">No log entries yet. Run a debug or benchmark scenario.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => `
      <tr>
        <td class="mono">${log.log_id}</td>
        <td class="mono" style="color:var(--text-secondary)">${truncate(log.run_id, 10)}</td>
        <td class="mono" style="color:var(--blue)">${log.txn_id || '—'}</td>
        <td class="query-cell" title="${escapeAttr(log.query_text)}">${escapeHTML(log.query_text || '—')}</td>
        <td>${statusBadge(log.status)}</td>
        <td class="mono" style="color:var(--text-muted)">${log.latency_ms != null ? log.latency_ms + 'ms' : '—'}</td>
      </tr>`).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--danger);padding:1rem">${err.message}</td></tr>`;
  }
}

// ── Auto-refresh ──────────────────────────────────────────────────────────
function toggleAutoRefresh(e) {
  if (e.target.checked) {
    autoRefreshTimer = setInterval(fetchLogs, 3000);
    showToast('Auto-refresh enabled (3s interval)', 'info');
  } else {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
    showToast('Auto-refresh disabled', 'info');
  }
}

// ── Fetch history ─────────────────────────────────────────────────────────
async function fetchHistory() {
  const container = document.getElementById('history-container');
  container.innerHTML = `<div class="empty-state"><div class="empty-state-title" style="color:var(--text-muted)">Loading…</div></div>`;

  try {
    const data = await apiFetch('/benchmark-results?limit=50');
    const results = data.results || [];

    if (!results.length) {
      container.innerHTML = `
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
          <div class="empty-state-title">No benchmark runs yet</div>
          <div class="empty-state-desc">Go to Benchmark tab and run your first workload.</div>
        </div>`;
      return;
    }

    container.innerHTML = `
      <div class="table-wrap">
        <table role="grid" aria-label="Benchmark history">
          <thead>
            <tr>
              <th>Run #</th>
              <th>Pattern</th>
              <th>Isolation</th>
              <th>Concurrency</th>
              <th>Total</th>
              <th>Success</th>
              <th>Deadlocks</th>
              <th>Anomalies</th>
              <th>Avg Latency</th>
              <th>TPS</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${results.map(r => renderHistoryRow(r)).join('')}
          </tbody>
        </table>
      </div>`;

    // Bind expand rows
    container.querySelectorAll('.history-expand-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const runId = btn.dataset.runId;
        const detailRow = document.getElementById(`detail-${runId}`);
        const isOpen = detailRow.classList.contains('open');

        if (isOpen) {
          detailRow.classList.remove('open');
          btn.textContent = '▶';
          return;
        }

        btn.textContent = '▼';
        detailRow.innerHTML = '<td colspan="12" style="padding:1rem;color:var(--text-muted)">Loading…</td>';
        detailRow.classList.add('open');

        try {
          const detail = await apiFetch(`/benchmark-results/${runId}`);
          detailRow.innerHTML = `<td colspan="12">${renderDetail(detail)}</td>`;
        } catch {
          detailRow.innerHTML = `<td colspan="12" style="color:var(--danger)">Failed to load details.</td>`;
        }
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-title" style="color:var(--danger)">${err.message}</div></div>`;
  }
}

function renderHistoryRow(r) {
  const successPct = r.total_transactions
    ? Math.round((r.successful / r.total_transactions) * 100) : 0;

  return `
    <tr>
      <td>
        <button class="btn btn-sm btn-ghost history-expand-btn" data-run-id="${r.run_id}" aria-label="Expand run ${r.run_id}" style="min-height:28px;padding:4px 8px">
          ▶
        </button>
        <span class="mono" style="margin-left:6px">#${r.run_id}</span>
      </td>
      <td><span class="badge badge-purple">${r.pattern || '—'}</span></td>
      <td><span style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text-secondary)">${r.isolation_level || '—'}</span></td>
      <td class="mono">${r.concurrency_level}</td>
      <td class="mono">${fmt(r.total_transactions)}</td>
      <td>
        <span style="color:var(--accent);font-family:var(--font-mono);font-weight:600">${fmt(r.successful)}</span>
        <span style="color:var(--text-muted);font-size:0.75rem"> (${successPct}%)</span>
      </td>
      <td class="mono" style="color:${parseInt(r.deadlocks) > 0 ? 'var(--danger)' : 'var(--text-muted)'}">${r.deadlocks}</td>
      <td class="mono" style="color:${parseInt(r.anomalies_detected) > 0 ? 'var(--warning)' : 'var(--text-muted)'}">${r.anomalies_detected}</td>
      <td class="mono">${parseFloat(r.avg_latency_ms || 0).toFixed(1)}ms</td>
      <td class="mono">${parseFloat(r.throughput_tps || 0).toFixed(1)}</td>
      <td style="font-size:0.75rem;color:var(--text-muted)">${formatDate(r.timestamp)}</td>
    </tr>
    <tr id="detail-${r.run_id}" class="history-detail" style="display:none"></tr>`;
}

// Override to make detail rows visible
document.addEventListener('DOMContentLoaded', () => {
  // Override default display:none on history-detail after it opens
  const style = document.createElement('style');
  style.textContent = '.history-detail.open { display: table-row !important; }';
  document.head.appendChild(style);
});

function renderDetail(detail) {
  const { result, anomalies = [] } = detail;
  if (!anomalies.length) {
    return `<div style="padding:12px;color:var(--text-muted);font-size:0.875rem">No anomalies detected for this run.</div>`;
  }
  return `
    <div style="padding:12px">
      <div style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:8px">Anomalies</div>
      <div class="anomaly-list">
        ${anomalies.map(a => `
          <div class="anomaly-item ${a.type}" style="padding:10px 12px">
            <div class="anomaly-body">
              <div class="anomaly-type" style="font-size:0.8rem">${a.type?.replace(/_/g,' ')}</div>
              <div class="anomaly-desc" style="font-size:0.8rem">${a.description || ''}</div>
              ${a.txn_ids ? `<div class="anomaly-txns">Transactions: ${a.txn_ids}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>
    </div>`;
}

// ── Helpers ───────────────────────────────────────────────────────────────
function escapeHTML(str) {
  return (str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escapeAttr(str) {
  return (str ?? '').replace(/"/g, '&quot;');
}
function truncate(str, n) {
  if (!str) return '—';
  return str.length > n ? str.slice(0, n) + '…' : str;
}
function formatDate(ts) {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString('en-US', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return ts; }
}
