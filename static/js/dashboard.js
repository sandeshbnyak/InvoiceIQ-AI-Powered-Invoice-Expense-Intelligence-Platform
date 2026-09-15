const chartPalette = ['#c8f36a', '#7ca8ff', '#f7c66d', '#79dba7', '#c38cff', '#ff9b73', '#8e96a3'];
const readJson = (id) => JSON.parse(document.getElementById(id).textContent);

const spendingCanvas = document.getElementById('spendingChart');
if (spendingCanvas) {
  new Chart(spendingCanvas, {
    type: 'line',
    data: { labels: readJson('monthly-labels'), datasets: [{ data: readJson('monthly-values'), borderColor: '#c8f36a', backgroundColor: 'rgba(200,243,106,.08)', fill: true, tension: .38, pointRadius: 3, pointBackgroundColor: '#c8f36a', pointBorderColor: '#191c20', pointBorderWidth: 2 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { displayColors: false, callbacks: { label: (context) => ` ₹${context.raw.toLocaleString('en-IN')}` } } }, scales: { x: { grid: { display: false }, ticks: { color: '#69717e', font: { size: 10 } } }, y: { beginAtZero: true, grid: { color: '#2a2f36' }, ticks: { color: '#69717e', font: { size: 10 }, callback: (value) => `₹${(value / 1000).toFixed(0)}k` } } } }
  });
}

const categoryCanvas = document.getElementById('categoryChart');
if (categoryCanvas) {
  const labels = readJson('category-labels');
  new Chart(categoryCanvas, { type: 'doughnut', data: { labels, datasets: [{ data: readJson('category-values'), backgroundColor: chartPalette, borderColor: '#191c20', borderWidth: 4 }] }, options: { cutout: '76%', maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => ` ${context.label}: ₹${context.raw.toLocaleString('en-IN')}` } } } } });
  document.getElementById('categoryLegend').innerHTML = labels.map((label, index) => `<div class="legend-item"><span class="legend-swatch" style="background:${chartPalette[index]}"></span>${label}</div>`).join('');
}

const sidebarToggle = document.getElementById('sidebarToggle');
if (sidebarToggle) sidebarToggle.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));
