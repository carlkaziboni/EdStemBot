/**
 * EdStemBot Lecturer Dashboard — Main Client Script
 */

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

async function initDashboard() {
  // Check what charts or elements are on the current page
  if (document.getElementById('topicBarChart')) {
    loadTopicDistribution();
  }
  if (document.getElementById('topicDonutChart')) {
    loadTopicDonut();
  }
  if (document.getElementById('trendLineChart')) {
    loadTopicTrends();
  }
  if (document.getElementById('activityHeatmap')) {
    loadActivityHeatmap();
  }

  // Render Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Set up periodic polling for live data (every 30 seconds)
  setInterval(() => {
    refreshKPIs();
  }, 30000);
}

async function loadTopicDistribution() {
  try {
    const res = await fetch('/api/v1/topics/distribution?limit=10');
    if (!res.ok) return;
    const data = await res.json();
    renderTopicBarChart('topicBarChart', data);
  } catch (err) {
    console.error('Failed to load topic distribution:', err);
  }
}

async function loadTopicDonut() {
  try {
    const res = await fetch('/api/v1/topics/distribution?limit=6');
    if (!res.ok) return;
    const data = await res.json();
    renderTopicDonutChart('topicDonutChart', data);
  } catch (err) {
    console.error('Failed to load topic donut:', err);
  }
}

async function loadTopicTrends() {
  try {
    const res = await fetch('/api/v1/topics/trends?days=7');
    if (!res.ok) return;
    const data = await res.json();
    renderTrendLineChart('trendLineChart', data);
  } catch (err) {
    console.error('Failed to load topic trends:', err);
  }
}

async function loadActivityHeatmap() {
  try {
    const res = await fetch('/api/v1/activity/heatmap');
    if (!res.ok) return;
    const data = await res.json();
    renderActivityHeatmap('activityHeatmap', data);
  } catch (err) {
    console.error('Failed to load heatmap:', err);
  }
}

async function refreshKPIs() {
  try {
    const res = await fetch('/api/v1/kpis');
    if (!res.ok) return;
    const kpis = await res.json();
    
    updateCounter('kpi-total-questions', kpis.total_questions);
    updateCounter('kpi-unique-students', kpis.unique_students);
    updateCounter('kpi-questions-today', kpis.questions_today);
    updateCounter('kpi-distinct-topics', kpis.distinct_topics);
  } catch (err) {
    console.error('Failed to refresh KPIs:', err);
  }
}

function updateCounter(elementId, newValue) {
  const el = document.getElementById(elementId);
  if (el && newValue !== undefined) {
    el.innerText = newValue;
  }
}
