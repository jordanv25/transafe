import { $, S, esc, fmtClock, ago, sevPill, catDot, catName, spark, feedItem, api } from './core.js';
import { openIssue } from './issues.js';

let map, layer, chTimeline, chDonut;

export function initDashboard() {
  map = L.map('map', { zoomControl: true, attributionControl: true }).setView([12.9716, 77.5946], 11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap contributors' }).addTo(map);
  layer = L.layerGroup().addTo(map);
  Chart.defaults.color = '#aab5c4'; Chart.defaults.borderColor = '#263041'; Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  chTimeline = new Chart($('#chTimeline'), {
    type: 'bar', data: { labels: [], datasets: [] },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      scales: { x: { stacked: true, grid: { display: false }, ticks: { maxTicksLimit: 7 } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } },
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      datasets: { bar: { borderSkipped: false, borderRadius: 2 } } },
  });
  chDonut = new Chart($('#chDonut'), {
    type: 'doughnut', data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderColor: '#151b24', borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '62%', animation: false, plugins: { legend: { display: false } } },
  });
  $('#feedFilter').addEventListener('change', (e) => { S.filter = e.target.value; renderFeed(); });
  $('#feedList').addEventListener('click', (e) => {
    const f = e.target.closest('.fi'); if (!f) return;
    document.dispatchEvent(new CustomEvent('analyze-text', { detail: f.dataset.text }));
  });
}

export function fillFilters() {
  for (const sel of ['#feedFilter', '#issueCat']) {
    const el = $(sel);
    el.innerHTML = '<option value="">All categories</option>' + S.meta.actionable.map((c) => `<option value="${c}">${esc(catName(c))}</option>`).join('');
  }
  $('#mapLegend').innerHTML = S.meta.actionable.map((c) => `<span>${catDot(c)}${esc(catName(c))}</span>`).join('');
}

export function renderSnapshot(s) {
  S.snap = s;
  $('#simClock').textContent = fmtClock(s.now) + ' · ' + s.speed + '×';
  $('#btnPlay').textContent = s.running ? '❚❚' : '▶';
  renderKpis(s); renderMap(s); renderEmerging(s); renderTimeline(s); renderDonut(s); renderTopIssues(s);
}

function renderKpis(s) {
  const k = s.kpis;
  const cards = [
    ['Complaints (1 h)', k.last_hour, `${k.total.toLocaleString()} processed in total`],
    ['Rate', k.rate_per_min + '/min', 'rolling 1-hour average'],
    ['Avg severity', k.avg_severity, 'scale 0–100'],
    ['Critical (1 h)', k.critical, 'severity ≥ 78'],
    ['Open issues', k.open_issues, 'clusters active in last 6 h'],
    ['Emerging bursts', k.emerging, 'statistically unusual surges'],
    ['Pipeline latency', k.latency_ms + ' ms', 'per complaint, end-to-end'],
  ];
  $('#kpis').innerHTML = cards.map(([l, v, sub]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div><div class="s">${sub}</div></div>`).join('');
}

function renderMap(s) {
  layer.clearLayers();
  for (const h of s.hotspots) {
    const loc = (S.places || {})[h.name]; if (!loc) continue;
    const color = S.colors[h.top_category];
    const r = 7 + Math.sqrt(h.count) * 3.2;
    const m = L.circleMarker([loc.lat, loc.lng], { radius: r, color: h.avg_severity >= 55 ? '#fff' : color, weight: h.avg_severity >= 55 ? 2 : 1, fillColor: color, fillOpacity: 0.55 }).addTo(layer);
    const rows = Object.entries(h.categories).sort((a, b) => b[1] - a[1]).map(([c, n]) => `${catDot(c)}${esc(catName(c))}: <b>${n}</b>`).join('<br>');
    m.bindTooltip(`<b>${esc(h.name)}</b><br>${h.count} complaints · avg severity ${h.avg_severity}<br>${rows}`);
  }
}

function renderEmerging(s) {
  const e = s.emerging;
  $('#calibTag').hidden = !e.calibrating;
  if (!e.items.length) { $('#emergingList').innerHTML = '<div class="muted">No unusual surges right now. Try <b>Inject</b> to simulate an incident.</div>'; return; }
  $('#emergingList').innerHTML = e.items.map((r) => `<div class="item"><div class="main"><div class="t">${esc(r.label)}</div>
    <div class="m">${r.kind} · ${r.recent} in 30 min vs ~${r.expected} expected · z=${r.z}</div></div>
    <div class="r"><div class="up">▲ ${r.growth_pct > 999 ? '999+' : r.growth_pct}%</div>${spark(r.spark, '#e66767')}</div></div>`).join('');
}

function renderTimeline(s) {
  const t = s.timeline;
  chTimeline.data.labels = t.labels.map(fmtClock);
  chTimeline.data.datasets = S.meta.actionable.map((c) => ({ label: catName(c), data: t.series[c], backgroundColor: S.colors[c], borderColor: '#151b24', borderWidth: 1 }));
  chTimeline.update('none');
}

function renderDonut(s) {
  const cats = S.meta.actionable, vals = cats.map((c) => s.categories[c] || 0), tot = vals.reduce((a, b) => a + b, 0) || 1;
  chDonut.data.labels = cats.map(catName);
  chDonut.data.datasets[0].data = vals; chDonut.data.datasets[0].backgroundColor = cats.map((c) => S.colors[c]);
  chDonut.update('none');
  $('#catLegend').innerHTML = cats.map((c, i) => `<div><span>${catDot(c)}${esc(catName(c))}</span><b>${vals[i]} <span class="muted">(${Math.round(100 * vals[i] / tot)}%)</span></b></div>`).join('');
}

function renderTopIssues(s) {
  $('#topIssues').innerHTML = s.issues.slice(0, 6).map((i) => `<div class="item" data-id="${i.id}"><div class="main"><div class="t">${catDot(i.category)}${esc(i.title)}</div>
    <div class="m">${i.count} complaints · ${i.recent} in last hour · ${esc(i.keywords.slice(0, 2).join(', ') || '—')}</div>
    <div class="bar"><i style="width:${Math.min(100, i.priority * 6)}%"></i></div></div><div class="r">${sevPill(i.avg_severity >= 78 ? 'critical' : i.avg_severity >= 55 ? 'high' : i.avg_severity >= 30 ? 'medium' : 'low', i.avg_severity)}</div></div>`).join('')
    || '<div class="muted">Waiting for data…</div>';
  document.querySelectorAll('#topIssues .item').forEach((el) => el.onclick = () => openIssue(+el.dataset.id));
}

export function renderFeed() {
  const rows = S.feed.filter((c) => !S.filter || c.category === S.filter).slice(0, 40);
  $('#feedList').innerHTML = rows.map((c) => feedItem(c)).join('') || '<div class="muted">No complaints yet.</div>';
}

export function pushComplaint(c) {
  S.feed.unshift(c); S.feed = S.feed.slice(0, 120);
  if (S.filter && c.category !== S.filter) return;
  const list = $('#feedList');
  if (list.querySelector('.muted')) list.innerHTML = '';
  list.insertAdjacentHTML('afterbegin', feedItem(c, true));
  while (list.children.length > 40) list.lastElementChild.remove();
}
