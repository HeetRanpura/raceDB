/**
 * RaceDB — Debug.js (Scenario Mode)
 */
import { apiFetch, setLoading, showToast, statusBadge, anomalyClass, anomalyIcon } from './app.js';

// ── Scenarios ─────────────────────────────────────────────────────────────
const SCENARIOS = {
  'dirty-read': {
    isolation_level: 'READ UNCOMMITTED',
    transactions: {
      T1: [
        { step: 1, query: 'UPDATE accounts SET balance = balance - 500 WHERE account_id = 3' },
        { step: 3, query: 'ROLLBACK' }
      ],
      T2: [
        { step: 2, query: 'SELECT balance FROM accounts WHERE account_id = 3' },
        { step: 4, query: 'COMMIT' }
      ]
    }
  },
  'lost-update': {
    isolation_level: 'READ COMMITTED',
    transactions: {
      T1: [
        { step: 1, query: 'SELECT balance FROM accounts WHERE account_id = 1' },
        { step: 3, query: 'UPDATE accounts SET balance = balance - 200 WHERE account_id = 1' },
        { step: 5, query: 'COMMIT' }
      ],
      T2: [
        { step: 2, query: 'SELECT balance FROM accounts WHERE account_id = 1' },
        { step: 4, query: 'UPDATE accounts SET balance = balance - 100 WHERE account_id = 1' },
        { step: 6, query: 'COMMIT' }
      ]
    }
  },
  'phantom-read': {
    isolation_level: 'READ COMMITTED',
    transactions: {
      T1: [
        { step: 1, query: 'SELECT balance FROM accounts WHERE account_id = 5' },
        { step: 3, query: 'SELECT balance FROM accounts WHERE account_id = 5' },
        { step: 5, query: 'COMMIT' }
      ],
      T2: [
        { step: 2, query: 'UPDATE accounts SET balance = balance + 1000 WHERE account_id = 5' },
        { step: 4, query: 'COMMIT' }
      ]
    }
  }
};

const TXN_COLORS = [
  { dot: '#22C55E', badge: 'badge-success', cls: 'T1' },
  { dot: '#3B82F6', badge: 'badge-blue',    cls: 'T2' },
  { dot: '#8B5CF6', badge: 'badge-purple',  cls: 'T3' },
  { dot: '#F59E0B', badge: 'badge-warning', cls: 'T4' },
];

export function initDebug() {
  document.getElementById('scenario-dirty-read').addEventListener('click', (e) => runScenario('dirty-read', e.currentTarget));
  document.getElementById('scenario-lost-update').addEventListener('click', (e) => runScenario('lost-update', e.currentTarget));
  document.getElementById('scenario-phantom-read').addEventListener('click', (e) => runScenario('phantom-read', e.currentTarget));
}

async function runScenario(scenarioKey, btnElement) {
  const data = SCENARIOS[scenarioKey];
  const resultsPanel = document.getElementById('debug-results');

  // Reset all buttons visual state
  document.querySelectorAll('#panel-debug .btn-secondary').forEach(b => b.style.borderColor = 'var(--border)');
  btnElement.style.borderColor = 'var(--accent)';

  setLoading(btnElement, true);
  
  resultsPanel.innerHTML = `
    <div class="empty-state">
      <div class="progress-wrap" style="width:100%;max-width:300px">
        <div class="progress-bar animated" style="width:100%"></div>
      </div>
      <div class="empty-state-title">Executing Scenario...</div>
    </div>`;

  try {
    const res = await apiFetch('/run-debug', {
      method: 'POST',
      body: JSON.stringify(data),
    });

    renderDebugResults(res, data.isolation_level);
    showToast(`Scenario executed — ${res.summary?.anomalies_found || 0} anomalies found`, 'success');
  } catch (err) {
    showToast(`Execution failed: ${err.message}`, 'error');
    resultsPanel.innerHTML = `<div class="empty-state"><div class="empty-state-title" style="color:var(--danger)">${err.message}</div></div>`;
  } finally {
    setLoading(btnElement, false);
  }
}

function renderDebugResults(res, isolationLevel) {
  const panel = document.getElementById('debug-results');
  const { steps = [], anomalies = [], summary = {} } = res;

  const txnNames = [...new Set(steps.map(s => s.txn_id))];

  const summaryHTML = `
    <div class="metric-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:1.5rem">
      <div class="metric-card blue">
        <div class="metric-label">Total Steps</div>
        <div class="metric-value">${summary.total_steps ?? steps.length}</div>
      </div>
      <div class="metric-card success">
        <div class="metric-label">Successful</div>
        <div class="metric-value">${summary.successful ?? 0}</div>
      </div>
      <div class="metric-card danger">
        <div class="metric-label">Failed</div>
        <div class="metric-value">${summary.failed ?? 0}</div>
      </div>
      <div class="metric-card warning">
        <div class="metric-label">Anomalies</div>
        <div class="metric-value">${anomalies.length}</div>
      </div>
    </div>`;

  const timelineItems = steps.map((step, idx) => {
    const colorIdx = txnNames.indexOf(step.txn_id);
    const col = TXN_COLORS[colorIdx] || TXN_COLORS[0];
    const statusClass = step.status?.toLowerCase() || 'success';
    const resultText = step.result_rows?.length
      ? `<div class="tl-rows">${step.result_rows.length} row(s) returned: ${JSON.stringify(step.result_rows).substring(0, 80)}</div>`
      : '';
    const errorText = step.error
      ? `<div class="tl-error">${step.error}</div>` : '';

    return `
      <div class="timeline-item ${statusClass}" style="animation-delay:${idx * 40}ms">
        <div class="tl-step-badge" style="background:${col.dot}22;color:${col.dot}">
          ${step.step}
        </div>
        <div class="tl-content">
          <div class="tl-header">
            <div class="tl-txn-tag" style="background:${col.dot}22;color:${col.dot};padding:2px 8px;border-radius:100px;font-size:0.7rem;font-weight:700;font-family:var(--font-mono)">
              ${step.txn_id}
            </div>
            ${statusBadge(step.status)}
            <div class="tl-latency">${step.latency_ms != null ? step.latency_ms + 'ms' : '—'}</div>
          </div>
          <div class="tl-query">${escapeHTML(step.query)}</div>
          ${resultText}
          ${errorText}
        </div>
      </div>`;
  }).join('');

  const anomalyHTML = anomalies.length
    ? `<div class="card" style="margin-top:1.5rem">
        <div class="card-title">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.07 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
          Anomalies Detected — ${anomalies.length}
        </div>
        <div class="anomaly-list">
          ${anomalies.map(a => renderAnomalyItem(a)).join('')}
        </div>
      </div>` : '';

  panel.innerHTML = `
    ${summaryHTML}
    <div class="card">
      <div class="card-title">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        Execution Timeline — Defaulting to ${isolationLevel}
      </div>
      <div class="timeline">${timelineItems}</div>
    </div>
    ${anomalyHTML}`;
}

function renderAnomalyItem(a) {
  const c = anomalyClass(a.type);
  const color = c === 'danger' ? 'var(--danger)' : c === 'warning' ? 'var(--warning)' : c === 'purple' ? 'var(--purple)' : 'var(--blue)';
  return `
    <div class="anomaly-item ${a.type}">
      <div class="anomaly-icon" style="color:${color}">
        ${anomalyIcon(a.type)}
      </div>
      <div class="anomaly-body">
        <div class="anomaly-type">${a.type?.replace(/_/g, ' ')}</div>
        <div class="anomaly-desc">${a.description || ''}</div>
        ${a.txn_ids ? `<div class="anomaly-txns">Transactions: ${a.txn_ids}</div>` : ''}
      </div>
    </div>`;
}

function escapeHTML(str) {
  return (str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
