/**
 * RaceDB — Query Console Module
 * Handles SQL query execution, results rendering, and ER diagram visualization
 */
import { showToast, setLoading } from './app.js';

const API = 'http://localhost:8000';
let erDiagramLoaded = false;

// ── Example queries for quick access ────────────────────────────────
const EXAMPLE_QUERIES = [
  {
    label: 'All Users',
    sql: 'SELECT * FROM users;',
  },
  {
    label: 'Accounts + Users (JOIN)',
    sql: `SELECT a.account_id, u.first_name, u.last_name, a.account_type, a.balance
FROM accounts a
JOIN users u ON a.user_id = u.user_id;`,
  },
  {
    label: 'Loans with Branch & Bank',
    sql: `SELECT l.loan_id, u.first_name, u.last_name, l.loan_type,
       l.principal, l.interest_rate, b.branch_name, bk.bank_name
FROM loans l
JOIN users u    ON l.user_id   = u.user_id
JOIN branches b ON l.branch_id = b.branch_id
JOIN banks bk   ON b.bank_id   = bk.bank_id
WHERE l.status = 'ACTIVE';`,
  },
  {
    label: 'Cards + Account Owners',
    sql: `SELECT c.card_number, c.card_type, c.daily_limit, c.is_active,
       a.owner, a.balance
FROM cards c
JOIN accounts a ON c.account_id = a.account_id;`,
  },
  {
    label: 'Total Balance per Bank',
    sql: `SELECT bk.bank_name, COUNT(a.account_id) AS num_accounts,
       SUM(a.balance) AS total_balance
FROM accounts a
JOIN branches b ON a.branch_id = b.branch_id
JOIN banks bk   ON b.bank_id   = bk.bank_id
GROUP BY bk.bank_name;`,
  },
];

// ── Initialize Playground ───────────────────────────────────────────
export function initPlayground() {
  const runBtn = document.getElementById('playground-run-btn');
  const clearBtn = document.getElementById('playground-clear-btn');
  const editor = document.getElementById('sql-editor');

  if (!runBtn || !editor) return;

  runBtn.addEventListener('click', () => executeQuery());
  clearBtn?.addEventListener('click', () => clearResults());

  // Ctrl+Enter to run
  editor.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      executeQuery();
    }
  });

  // Populate example query buttons
  renderExampleQueries();

  // Load ER diagram when the tab becomes visible
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      if (tab.dataset.tab === 'playground' && !erDiagramLoaded) {
        // Small delay so the panel is visible before mermaid renders
        setTimeout(() => loadERDiagram(), 300);
      }
    });
  });
}

// ── Example Query Buttons ───────────────────────────────────────────
function renderExampleQueries() {
  const container = document.getElementById('example-queries');
  if (!container) return;

  EXAMPLE_QUERIES.forEach((q) => {
    const btn = document.createElement('button');
    btn.className = 'btn btn-sm btn-ghost example-query-btn';
    btn.textContent = q.label;
    btn.addEventListener('click', () => {
      document.getElementById('sql-editor').value = q.sql;
    });
    container.appendChild(btn);
  });
}

// ── Execute Query ───────────────────────────────────────────────────
async function executeQuery() {
  const editor = document.getElementById('sql-editor');
  const btn = document.getElementById('playground-run-btn');
  const sql = editor.value.trim();

  if (!sql) {
    showToast('Please enter a SQL query', 'error');
    return;
  }

  setLoading(btn, true);
  const statusEl = document.getElementById('query-status');
  statusEl.textContent = 'Executing…';
  statusEl.className = 'query-status running';

  try {
    const res = await fetch(`${API}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql }),
    });

    const data = await res.json();

    if (!res.ok) {
      const errMsg = data.detail || `HTTP ${res.status}`;
      statusEl.textContent = `Error`;
      statusEl.className = 'query-status error';
      showToast(errMsg, 'error');
      renderError(errMsg);
      return;
    }

    statusEl.textContent = data.message;
    statusEl.className = 'query-status success';

    if (data.columns && data.columns.length > 0) {
      renderTable(data.columns, data.rows);
    } else {
      renderMessage(data.message);
    }

    showToast(data.message, 'success');
  } catch (err) {
    statusEl.textContent = `Error`;
    statusEl.className = 'query-status error';
    showToast(`Query failed: ${err.message}`, 'error');
    renderError(err.message);
  } finally {
    setLoading(btn, false);
  }
}

// ── Render Results Table ────────────────────────────────────────────
function renderTable(columns, rows) {
  const container = document.getElementById('query-results');

  const headerCells = columns.map((c) => `<th scope="col">${escapeHtml(c)}</th>`).join('');
  const bodyRows = rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${cell === null ? '<span class="null-val">NULL</span>' : escapeHtml(String(cell))}</td>`).join('')}</tr>`
    )
    .join('');

  container.innerHTML = `
    <div class="table-wrap query-table-wrap">
      <table role="grid" aria-label="Query results">
        <thead><tr>${headerCells}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>
    <div class="query-row-count">${rows.length} row(s) returned</div>
  `;
}

function renderMessage(msg) {
  const container = document.getElementById('query-results');
  container.innerHTML = `
    <div class="query-message-box">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      <span>${escapeHtml(msg)}</span>
    </div>
  `;
}

function renderError(msg) {
  const container = document.getElementById('query-results');
  container.innerHTML = `
    <div class="query-error-box">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      <span>${escapeHtml(msg)}</span>
    </div>
  `;
}

function clearResults() {
  const container = document.getElementById('query-results');
  const statusEl = document.getElementById('query-status');
  container.innerHTML = `
    <div class="empty-state cinematic-empty" style="min-height:12rem">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/></svg>
      <div class="empty-state-title">Results will appear here</div>
      <div class="empty-state-desc">Write a SQL query above and press Run or Ctrl+Enter.</div>
    </div>
  `;
  statusEl.textContent = 'Ready';
  statusEl.className = 'query-status';
}

// ── ER Diagram Rendering ────────────────────────────────────────────
async function loadERDiagram() {
  const container = document.getElementById('er-diagram-container');
  if (!container) return;

  try {
    const res = await fetch(`${API}/api/schema-info`);
    const data = await res.json();

    if (!res.ok) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-desc">Failed to load schema.</div></div>`;
      return;
    }

    const mermaidCode = buildERMermaid(data.tables, data.foreign_keys);

    // Use a unique ID for mermaid rendering
    const diagramId = 'er-diagram-' + Date.now();
    container.innerHTML = `<div class="mermaid" id="${diagramId}">${mermaidCode}</div>`;

    // Mermaid v10+ uses mermaid.run() instead of deprecated mermaid.init()
    if (window.mermaid) {
      try {
        await window.mermaid.run({
          nodes: [document.getElementById(diagramId)],
        });
        erDiagramLoaded = true;
      } catch (mermaidErr) {
        console.error('Mermaid render error:', mermaidErr);
        container.innerHTML = `
          <div class="er-fallback">
            <div class="er-fallback-title">Entity-Relationship Diagram</div>
            ${buildERFallbackHTML(data.tables, data.foreign_keys)}
          </div>`;
        erDiagramLoaded = true;
      }
    }
  } catch (err) {
    console.error('ER diagram load error:', err);
    container.innerHTML = `<div class="empty-state"><div class="empty-state-desc">Could not connect to backend for schema info.</div></div>`;
  }
}

function buildERMermaid(tables, foreignKeys) {
  let lines = ['erDiagram'];

  const domainTables = ['users', 'banks', 'branches', 'accounts', 'cards', 'loans'];

  for (const [tableName, columns] of Object.entries(tables)) {
    if (!domainTables.includes(tableName)) continue;

    lines.push(`    ${tableName} {`);
    for (const col of columns) {
      // Clean type: remove size params and quotes from ENUM
      let typeStr = col.type
        .replace(/\(.*?\)/g, '')
        .replace(/'/g, '')
        .toUpperCase()
        .replace(/\s+/g, '_');
      if (!typeStr) typeStr = 'OTHER';

      const keyMark = col.key === 'PRI' ? 'PK' : col.key === 'MUL' ? 'FK' : col.key === 'UNI' ? 'UK' : '';
      const comment = keyMark ? ` "${keyMark}"` : '';
      lines.push(`        ${typeStr} ${col.name}${comment}`);
    }
    lines.push('    }');
  }

  // Add relationships
  for (const fk of foreignKeys) {
    if (!domainTables.includes(fk.table) || !domainTables.includes(fk.ref_table)) continue;
    lines.push(`    ${fk.ref_table} ||--o{ ${fk.table} : "${fk.column}"`);
  }

  return lines.join('\n');
}

// ── Fallback HTML ER Diagram (if Mermaid fails) ─────────────────────
function buildERFallbackHTML(tables, foreignKeys) {
  const domainTables = ['users', 'banks', 'branches', 'accounts', 'cards', 'loans'];
  let html = '<div class="er-tables-grid">';

  for (const [tableName, columns] of Object.entries(tables)) {
    if (!domainTables.includes(tableName)) continue;

    html += `<div class="er-table-card">`;
    html += `<div class="er-table-name">${tableName}</div>`;
    html += `<div class="er-table-cols">`;
    for (const col of columns) {
      const keyIcon = col.key === 'PRI' ? '🔑' : col.key === 'MUL' ? '🔗' : col.key === 'UNI' ? '◆' : '';
      html += `<div class="er-col-row">
        <span class="er-col-key">${keyIcon}</span>
        <span class="er-col-name">${col.name}</span>
        <span class="er-col-type">${col.type}</span>
      </div>`;
    }
    html += `</div></div>`;
  }

  html += '</div>';

  // Relationships
  if (foreignKeys.length > 0) {
    html += '<div class="er-relationships">';
    html += '<div class="er-rel-title">Relationships</div>';
    for (const fk of foreignKeys) {
      if (!domainTables.includes(fk.table) || !domainTables.includes(fk.ref_table)) continue;
      html += `<div class="er-rel-row">
        <span class="er-rel-from">${fk.ref_table}.${fk.ref_column}</span>
        <span class="er-rel-arrow">→</span>
        <span class="er-rel-to">${fk.table}.${fk.column}</span>
      </div>`;
    }
    html += '</div>';
  }

  return html;
}

// ── Utility ─────────────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
