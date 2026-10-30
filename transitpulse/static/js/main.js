import { $, $$, S, api, toast, esc } from './core.js';
import { initDashboard, fillFilters, renderSnapshot, renderFeed, pushComplaint } from './dashboard.js';
import { initIssues, loadIssues } from './issues.js';
import { initAnalyzer } from './analyzer.js';
import { loadModel } from './model.js';

function showPage(name) {
  $$('.page').forEach((p) => p.classList.toggle('active', p.id === 'page-' + name));
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.page === name));
  if (name === 'issues') loadIssues();
  if (name === 'model') loadModel();
  if (name === 'dashboard') setTimeout(() => window.dispatchEvent(new Event('resize')), 50);
}

function connect() {
  const es = new EventSource('/api/stream');
  const pill = $('#livePill');
  es.onopen = () => { pill.classList.add('on'); $('#liveText').textContent = 'live'; };
  es.onerror = () => { pill.classList.remove('on'); $('#liveText').textContent = 'reconnecting'; };
  es.onmessage = (m) => {
    const { event, data } = JSON.parse(m.data);
    if (event === 'snapshot') renderSnapshot(data);
    else if (event === 'complaint') pushComplaint(data);
    else if (event === 'incident') toast(`<b>Incident injected</b><br>${esc(data.name)} near ${esc(data.location)}`);
  };
}

async function boot() {
  const meta = await api('/api/meta');
  S.meta = meta; S.places = meta.places;
  for (const c of meta.categories) { S.colors[c.key] = c.color; S.labels[c.key] = c.label; }
  $('#selIncident').innerHTML = meta.scenarios.map((s) => `<option value="${s.key}">${esc(s.name)}</option>`).join('');
  initDashboard(); fillFilters(); initIssues(); initAnalyzer();
  $('#tabs').onclick = (e) => { const b = e.target.closest('button'); if (b) showPage(b.dataset.page); };
  document.addEventListener('click', (e) => { const a = e.target.closest('[data-goto]'); if (a) { e.preventDefault(); showPage(a.dataset.goto); } });
  $('#btnPlay').onclick = async () => { const r = await api('/api/simulator', { method: 'POST', body: { running: !S.snap.running } }); $('#btnPlay').textContent = r.running ? '❚❚' : '▶'; };
  $('#selSpeed').onchange = (e) => api('/api/simulator', { method: 'POST', body: { speed: +e.target.value } });
  $('#btnIncident').onclick = () => api('/api/simulator/incident', { method: 'POST', body: { kind: $('#selIncident').value } });
  const st = await api('/api/state');
  S.feed = st.feed; renderFeed(); renderSnapshot(st.snapshot);
  $('#selSpeed').value = String(st.snapshot.speed);
  connect();
}
boot().catch((e) => { document.body.insertAdjacentHTML('beforeend', `<pre style="color:#e66767;padding:20px">Failed to start: ${esc(e.message)}</pre>`); console.error(e); });
