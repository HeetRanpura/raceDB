/**
 * RaceDB — Debug.js
 * Step builder, debug execution, timeline rendering, anomaly display
 */
import { apiFetch, setLoading, showToast, statusBadge, anomalyClass, anomalyIcon } from './app.js';

// ── State ───────────────────────────────────────────────────────────────
const TXN_COLORS = [
  { dot: '#22C55E', badge: 'badge-success', cls: 'T1' },
  { dot: '#3B82F6', badge: 'badge-blue',    cls: 'T2' },
  { dot: '#8B5CF6', badge: 'badge-purple',  cls: 'T3' },
  { dot: '#F59E0B', badge: 'badge-warning', cls: 'T4' },
  { dot: '#06B6D4', badge: '',              cls: 'T5' },
];

let txnCount = 2;
let stepGlobal = 1;

// ── Init ─────────────────────────────────────────────────────────────────
export function initDebug() {
  // Render initial 2 transactions
  renderTxnBuilder();

  document.getElementById('add-txn-btn').addEventListener('click', () => {
    if (txnCount >= 5) { showToast('Maximum 5 transactions supported', 'info'); return; }
    txnCount++;
    renderTxnBuilder();
  });

  document.getElementById('remove-txn-btn').addEventListener('click', () => {
    if (txnCount <= 1) { showToast('Need at least 1 transaction', 'info'); return; }
    txnCount--;
    renderTxnBuilder();
  });

  document.getElementById('add-preset-btn').addEventListener('click', loadLostUpdatePreset);
  document.getElementById('run-debug-btn').addEventListener('click', runDebug);
}

// ── Preset: Lost Update scenario ─────────────────────────────────────────
function loadLostUpdatePreset() {
  txnCount = 2;
  stepGlobal = 6;

  const container = document.getElementById('txn-builder');
  container.innerHTML = buildTxnBlockHTML('T1', 0, [
    { step: 1, query: 'SELECT balance FROM accounts WHERE account_id = 1' },
    { step: 3, query: 'UPDATE accounts SET balance = balance - 200 WHERE account_id = 1' },
    { step: 5, query: 'COMMIT' },
  ]);
  container.innerHTML += buildTxnBlockHTML('T2', 1, [
    { step: 2, query: 'SELECT balance FROM accounts WHERE account_id = 1' },
    { step: 4, query: 'UPDATE accounts SET balance = balance - 100 WHERE account_id = 1' },
    { step: 6, query: 'COMMIT' },
  ]);

  bindStepButtons();
  showToast('Lost Update preset loaded', 'success');
}

// ── Build Txn Block HTML ─────────────────────────────────────────────────
function buildTxnBlockHTML(name, colorIdx, steps = []) {
  const col = TXN_COLORS[colorIdx] || TXN_COLORS[0];
  const stepsHTML = steps.map(s => stepRowHTML(name, s.step, s.query)).join('');
  return `
    <div class="txn-block" data-txn="${name}">
      <div class="txn-header">
        <div class="txn-name">
          <div class="txn-dot" style="background:${col.dot};box-shadow:0 0 8px ${col.dot}40"></div>
          Transaction ${name}
        </div>
        <button class="btn btn-sm btn-ghost add-step-btn" data-txn="${name}" aria-label="Add step to ${name}">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Add Step
        </button>
      </div>
      <div class="txn-steps" id="steps-${name}">${stepsHTML}</div>
    </div>`;
}

function stepRowHTML(txn, stepNum, query = '') {
  return `
    <div class="step-row" data-step="${stepNum}">
      <input type="number" class="step-num-input" value="${stepNum}" min="1" max="99"
             aria-label="Step order for ${txn}" title="Global execution order">
      <input type="text" class="step-query-input" value="${query}"
             placeholder="SQL query, COMMIT, or ROLLBACK"
             aria-label="SQL query for ${txn}" autocomplete="off" spellcheck="false">
      <button class="btn btn-sm btn-danger remove-step-btn" aria-label="Remove step">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>`;
}

// ── Render builder ───────────────────────────────────────────────────────
function renderTxnBuilder() {
  const container = document.getElementById('txn-builder');
  let html = '';
  for (let i = 0; i < txnCount; i++) {
    const name = `T${i + 1}`;
    // Preserve existing steps if already rendered
    const existing = container ? container.querySelector(`[data-txn="${name}"] .txn-steps`) : null;
    const stepsInner = existing ? existing.innerHTML : stepRowHTML(name, i * 2 + 1, '');
    html += buildTxnBlockHTML(name, i, []);
  }
  container.innerHTML = html;
  bindStepButtons();
}

function bindStepButtons() {
  document.querySelectorAll('.add-step-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const txn = btn.dataset.txn;
      const stepsContainer = document.getElementById(`steps-${txn}`);
      const nextStep = Math.max(...Array.from(
        stepsContainer.querySelectorAll('.step-num-input')
      ).map(i => parseInt(i.value) || 0), 0) + 1;
      stepsContainer.insertAdjacentHTML('beforeend', stepRowHTML(txn, nextStep, ''));
      bindRemoveButtons();
    });
  });
  bindRemoveButtons();
}

function bindRemoveButtons() {
  document.querySelectorAll('.remove-step-btn').forEach(btn => {
    btn.onclick = () => {
      const row = btn.closest('.step-row');
      const parent = row.parentElement;
      if (parent.querySelectorAll('.step-row').length <= 1) {
        showToast('Each transaction needs at least 1 step', 'info');
        return;
      }
      row.remove();
    };
  });
}

// ── Collect form data ─────────────────────────────────────────────────────
function collectFormData() {
  const isolationLevel = document.getElementById('debug-isolation').value;
  const transactions = {};

  document.querySelectorAll('.txn-block').forEach(block => {
    const txn = block.dataset.txn;
    const steps = [];
    block.querySelectorAll('.step-row').forEach(row => {
      const step = parseInt(row.querySelector('.step-num-input').value);
      const query = row.querySelector('.step-query-input').value.trim();
      if (query && !isNaN(step)) steps.push({ step, query });
    });
    if (steps.length) transactions[txn] = steps;
  });

  return { isolation_level: isolationLevel, transactions };
}

// ── Run Debug ──────────────────────────────────────────────────────────────
async function runDebug() {
  const btn = document.getElementById('run-debug-btn');
  const resultsPanel = document.getElementById('debug-results');
  const data = collectFormData();

  if (!Object.keys(data.transactions).length) {
    showToast('Add at least one transaction with steps', 'error');
    return;
  }

  setLoading(btn, true);
  resultsPanel.innerHTML = `
    <div class="empty-state">
      <div class="progress-wrap" style="width:100%;max-width:300px">
        <div class="progress-bar animated" style="width:100%"></div>
      </div>
      <div class="empty-state-title">Executing transactions…</div>
    </div>`;

  try {
    const res = await apiFetch('/run-debug', {
      method: 'POST',
      body: JSON.stringify(data),
    });

    renderDebugResults(res, data.isolation_level);
    showToast(`Debug run complete — ${res.summary?.anomalies_found || 0} anomalies found`, 'success');
  } catch (err) {
    showToast(`Debug failed: ${err.message}`, 'error');
    resultsPanel.innerHTML = `<div class="empty-state"><div class="empty-state-title" style="color:var(--danger)">${err.message}</div></div>`;
  } finally {
    setLoading(btn, false);
  }
}

// ── Render Results ─────────────────────────────────────────────────────────
function renderDebugResults(res, isolationLevel) {
  const panel = document.getElementById('debug-results');
  const { steps = [], anomalies = [], summary = {} } = res;

  const txnNames = [...new Set(steps.map(s => s.txn_id))];

  // Summary
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

  // Timeline
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
            <div class="tl-latency">${step.latency_ms}ms</div>
          </div>
          <div class="tl-query">${escapeHTML(step.query)}</div>
          ${resultText}
          ${errorText}
        </div>
      </div>`;
  }).join('');

  // Anomaly section
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
        Execution Timeline — ${isolationLevel}
      </div>
      <div class="timeline">${timelineItems}</div>
    </div>
    ${anomalyHTML}`;
}

function renderAnomalyItem(a) {
  return `
    <div class="anomaly-item ${a.type}">
      <div class="anomaly-icon" style="color:var(--${anomalyClass(a.type) === 'danger' ? 'danger' : anomalyClass(a.type) === 'warning' ? 'warning' : anomalyClass(a.type) === 'blue' ? 'blue' : 'purple'})">
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
