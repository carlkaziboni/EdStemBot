/**
 * EdStemBot Lecturer Dashboard — shadcn/ui themed Chart.js visualizer
 */

if (typeof Chart !== 'undefined') {
  Chart.defaults.color = 'hsl(240, 5%, 64.9%)'; // muted foreground
  Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
  Chart.defaults.font.size = 12;
  
  // shadcn tooltip style: compact, dark zinc card, 1px border
  Chart.defaults.plugins.tooltip.backgroundColor = 'hsl(240, 10%, 4.9%)';
  Chart.defaults.plugins.tooltip.titleColor = 'hsl(0, 0%, 98%)';
  Chart.defaults.plugins.tooltip.bodyColor = 'hsl(240, 5%, 64.9%)';
  Chart.defaults.plugins.tooltip.borderColor = 'hsl(240, 3.7%, 15.9%)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;
}

const SHADCN_PALETTE = [
  'hsl(221.2, 83.2%, 53.3%)', // chart-1 blue
  'hsl(199, 89%, 48%)',        // chart-2 sky
  'hsl(160, 84%, 39%)',        // chart-3 emerald
  'hsl(280, 65%, 60%)',        // chart-4 purple
  'hsl(35, 92%, 52%)',         // chart-5 amber
  'hsl(340, 75%, 55%)',
  'hsl(250, 70%, 65%)',
  'hsl(180, 60%, 45%)'
];

/**
 * Render horizontal bar chart of question counts per topic.
 */
function renderTopicBarChart(canvasId, items) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !items || !items.length) return null;

  const labels = items.map(d => d.topic);
  const data = items.map(d => d.count);

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Questions',
        data: data,
        backgroundColor: 'hsl(221.2, 83.2%, 53.3%)',
        borderRadius: 4,
        borderSkipped: false,
        barPercentage: 0.7,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { color: 'hsl(240, 3.7%, 12%)' },
          ticks: { precision: 0 }
        },
        y: {
          grid: { display: false },
          ticks: {
            font: { weight: 500 }
          }
        }
      }
    }
  });
}

/**
 * Render doughnut chart for topic distribution.
 */
function renderTopicDonutChart(canvasId, items) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !items || !items.length) return null;

  const topItems = items.slice(0, 6);
  const labels = topItems.map(d => d.topic);
  const data = topItems.map(d => d.count);

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: SHADCN_PALETTE.slice(0, labels.length),
        borderWidth: 2,
        borderColor: 'hsl(240, 10%, 4.9%)',
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 12 }
        }
      }
    }
  });
}

/**
 * Render 7-day trend line chart.
 */
function renderTrendLineChart(canvasId, trendData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !trendData || !trendData.length) return null;

  const dates = [...new Set(trendData.map(d => d.date))].sort();
  const topics = [...new Set(trendData.map(d => d.topic))].slice(0, 5);

  const datasets = topics.map((topic, idx) => {
    const color = SHADCN_PALETTE[idx % SHADCN_PALETTE.length];
    const data = dates.map(d => {
      const match = trendData.find(item => item.date === d && item.topic === topic);
      return match ? match.count : 0;
    });

    return {
      label: topic,
      data: data,
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
    };
  });

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { padding: 12 }
        }
      },
      scales: {
        x: {
          grid: { color: 'hsl(240, 3.7%, 12%)' }
        },
        y: {
          grid: { color: 'hsl(240, 3.7%, 12%)' },
          ticks: { precision: 0 }
        }
      }
    }
  });
}

/**
 * Render hourly activity heatmap using zinc cells.
 */
function renderActivityHeatmap(containerId, heatmapData) {
  const container = document.getElementById(containerId);
  if (!container || !heatmapData) return;

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  container.innerHTML = '';

  const maxVal = Math.max(1, ...heatmapData.map(d => d.count));

  days.forEach((dayName, dayIndex) => {
    const row = document.createElement('div');
    row.className = 'heatmap-row';

    const label = document.createElement('div');
    label.className = 'heatmap-label';
    label.innerText = dayName;
    row.appendChild(label);

    const cellsWrap = document.createElement('div');
    cellsWrap.className = 'heatmap-cells';

    for (let hour = 0; hour < 24; hour++) {
      const match = heatmapData.find(d => d.day === dayIndex && d.hour === hour);
      const count = match ? match.count : 0;
      const intensity = count / maxVal;

      const cell = document.createElement('div');
      cell.className = 'heatmap-cell';
      cell.title = `${dayName} ${hour}:00 — ${count} questions`;

      if (count > 0) {
        // Use chart-1 blue shades
        cell.style.backgroundColor = `hsla(221.2, 83.2%, 53.3%, ${Math.max(0.25, intensity)})`;
      }

      cellsWrap.appendChild(cell);
    }

    row.appendChild(cellsWrap);
    container.appendChild(row);
  });
}
