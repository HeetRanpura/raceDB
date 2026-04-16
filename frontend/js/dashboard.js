/**
 * RaceDB — Dashboard Module
 * Fetches and displays live aggregated system metrics on the dashboard tab.
 */
import { apiFetch, showToast, fmt } from './app.js';

const API = 'http://localhost:8000';
let dashboardInitialized = false;

// Format money
function formatCurrency(n) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

export function initDashboard() {
  const dashTab = document.querySelector('[data-tab="dashboard"]');
  if (!dashTab) return;

  // Load metrics when tab is clicked (or on first load if it's default)
  dashTab.addEventListener('click', () => {
    loadMetrics();
  });

  // If already selected on load
  if (dashTab.classList.contains('active')) {
    loadMetrics();
  }
}

async function loadMetrics() {
  const container = document.getElementById('panel-dashboard');
  if (!container) return;

  try {
    const data = await apiFetch('/api/dashboard-metrics');

    // 1. Total System Liquidity (Balance)
    animateValue('dash-liquidity', data.total_liquidity, true);

    // 2. Active Customers
    animateValue('dash-customers', data.active_customers, false);

    // 3. Total Loan Book
    animateValue('dash-loans', data.total_loan_book, true);

    // 4. Active Cards
    animateValue('dash-cards', data.active_cards, false);

    // 5. Account Breakdown
    renderAccountBreakdown(data.account_breakdown);

  } catch (err) {
    console.error('Failed to load dashboard metrics:', err);
    showToast('Failed to load dashboard metrics', 'error');
  }
}

function animateValue(id, end, isCurrency, duration = 1000) {
  const obj = document.getElementById(id);
  if (!obj) return;

  // Simple number animation
  let startTimestamp = null;
  const startObjValue = obj.dataset.val ? parseFloat(obj.dataset.val) : 0;
  
  if (startObjValue === end) return; // already there
  obj.dataset.val = end;

  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const easeOutQuart = 1 - Math.pow(1 - progress, 4);
    
    // Calculate current value based on easing
    const currentParam = startObjValue + (end - startObjValue) * easeOutQuart;
    
    obj.innerHTML = isCurrency ? formatCurrency(currentParam) : fmt(Math.round(currentParam));
    
    if (progress < 1) {
      window.requestAnimationFrame(step);
    } else {
      obj.innerHTML = isCurrency ? formatCurrency(end) : fmt(end);
    }
  };
  
  window.requestAnimationFrame(step);
}

function renderAccountBreakdown(breakdown) {
  const container = document.getElementById('dash-account-distribution');
  if (!container) return;

  if (!breakdown || breakdown.length === 0) {
    container.innerHTML = `<div class="empty-state-desc">No accounts found</div>`;
    return;
  }

  const icons = {
    'SAVINGS': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    'CURRENT': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>`,
    'SALARY':  `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`,
    'FIXED_DEPOSIT': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>`
  };

  const colors = {
    'SAVINGS': 'var(--blue)',
    'CURRENT': 'var(--accent)',
    'SALARY': 'var(--purple)',
    'FIXED_DEPOSIT': 'var(--warning)'
  };

  const total = breakdown.reduce((sum, item) => sum + item.count, 0);

  let html = `<div class="dash-breakdown-list">`;
  
  breakdown.forEach(item => {
    const pct = total > 0 ? (item.count / total) * 100 : 0;
    const icon = icons[item.account_type] || icons['SAVINGS'];
    const color = colors[item.account_type] || 'var(--text-secondary)';

    html += `
      <div class="dash-breakdown-item">
        <div class="dash-breakdown-icon" style="color: ${color}">${icon}</div>
        <div class="dash-breakdown-info">
          <div class="dash-breakdown-type">${item.account_type.replace('_', ' ')}</div>
          <div class="dash-breakdown-meta">${item.count} accounts</div>
        </div>
        <div class="dash-breakdown-pct" style="color: ${color}">${Math.round(pct)}%</div>
      </div>
      <div class="dash-breakdown-bar-bg">
        <div class="dash-breakdown-bar-fg" style="width: ${pct}%; background-color: ${color}; box-shadow: 0 0 8px ${color}"></div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}
