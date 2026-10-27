/* Home page logic. Data comes from the Python bridge (ui/bridge.py);
   the SAMPLE_* values are only used when the page is opened in a plain browser. */
const SAMPLE_STATS = { total: 1248, month: 86, amount: 125430, storage: '2.4 GB' };
const SAMPLE_COMPARISON = {
  labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
  lastMonth: [22000, 28000, 25000, 31000],
  thisMonth: [26000, 32000, 29000, 38430],
  growth: 14.2
};
const SAMPLE_PROJECTION = {
  labels: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov (Proj)', 'Dec (Proj)'],
  actual: [95000, 102000, 110000, 118000, 125430, 131000, null, null],
  projected: [null, null, null, null, null, 131000, 138000, 149000]
};

const $ = (id) => document.getElementById(id);
const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
const textColor = isDark ? '#9a9aa5' : '#6b7280';
const gridColor = isDark ? '#2f2f37' : '#e5e7eb';
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'top', labels: { color: textColor } } },
  scales: {
    x: { ticks: { color: textColor }, grid: { display: false } },
    y: { ticks: { color: textColor }, grid: { color: gridColor } }
  }
};
let projectionChart = null;

async function renderStats() {
  const s = (await App.api('getStats')) || SAMPLE_STATS;
  $('sTotal').textContent = s.total.toLocaleString('en-US');
  $('sMonth').textContent = s.month.toLocaleString('en-US');
  $('sAmount').textContent = App.peso(s.amount).replace(/\.00$/, '');
  $('sStorage').textContent = s.storage;
}

// 1. Monthly Sales Comparison Chart
async function renderComparison() {
  const c = (await App.api('getMonthlyComparison')) || SAMPLE_COMPARISON;
  if (c.growth !== null) {
    $('growth').textContent = `${c.growth >= 0 ? '+' : ''}${c.growth.toFixed(1)}% vs last month`;
    $('growth').hidden = false;
  }
  new Chart($('salesChart'), {
    type: 'bar',
    data: {
      labels: c.labels,
      datasets: [
        { label: 'Last Month (₱)', data: c.lastMonth, backgroundColor: isDark ? '#2a2650' : '#eeebfa', borderRadius: 6 },
        { label: 'This Month (₱)', data: c.thisMonth, backgroundColor: '#5443b0', borderRadius: 6 }
      ]
    },
    options: chartOptions
  });
}

// 2. Money Projection Line Chart
async function renderProjection() {
  const p = (await App.api('getProjection', Number($('projMonths').value))) || SAMPLE_PROJECTION;
  if (projectionChart) projectionChart.destroy();
  projectionChart = new Chart($('projectionChart'), {
    type: 'line',
    data: {
      labels: p.labels,
      datasets: [
        { label: 'Actual Revenue (₱)', data: p.actual, borderColor: '#5443b0', backgroundColor: 'rgba(84, 67, 176, 0.1)', fill: true, tension: 0.3 },
        { label: 'Projected Revenue (₱)', data: p.projected, borderColor: '#1b7f4b', borderDash: [5, 5], backgroundColor: 'rgba(27, 127, 75, 0.05)', fill: true, tension: 0.3 }
      ]
    },
    options: chartOptions
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const user = App.getSettings().username;
  $('name').textContent = user && user !== 'User' ? ' ' + user : '';
  $('signOut').addEventListener('click', App.signOut);
  $('projMonths').addEventListener('change', renderProjection);
  renderStats();
  renderComparison();
  renderProjection();
});
