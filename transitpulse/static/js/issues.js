import { $, S, api, esc, ago, sevPill, catDot, catName, spark, feedItem, fmtDay } from './core.js';

let timer;
const lvl = (v) => (v >= 78 ? 'critical' : v >= 55 ? 'high' : v >= 30 ? 'medium' : 'low');

export function initIssues() {
  $('#issueQ').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(loadIssues, 250); });
  $('#issueCat').addEventListener('change', loadIssues);
  $('#drawerClose').onclick = closeDrawer;
  document.addEventListener('keydown', (e) => e.key === 'Escape' && closeDrawer());
}

export async function loadIssues() {
  const q = $('#issueQ').value.trim(), cat = $('#issueCat').value;
  const rows = await api('/api/issues?' + new URLSearchParams({ ...(cat && { category: cat }), ...(q && { q }) }));
  $('#issueTable tbody').innerHTML = rows.map((i) => `<tr class="click" data-id="${i.id}">
    <td><b>${esc(i.title)}</b><div class="muted">${esc(i.keywords.slice(0, 3).join(' · '))}</div></td>
    <td>${catDot(i.category)}${esc(catName(i.category))}</td><td class="num">${i.count}</td><td class="num">${i.recent}</td>
    <td>${i.recent > i.previous ? '<span class="up">▲</span>' : i.recent < i.previous ? '▼' : '–'} <span class="muted">${i.previous}→${i.recent}</span></td>
    <td>${sevPill(lvl(i.avg_severity), i.avg_severity)}</td><td>${esc(i.locations.join(', ') || '—')}</td><td>${ago(i.last_seen)}</td></tr>`).join('')
    || '<tr><td colspan="8" class="muted">No issues match.</td></tr>';
  document.querySelectorAll('#issueTable tr.click').forEach((tr) => tr.onclick = () => openIssue(+tr.dataset.id));
  const box = $('#searchResults');
  if (q) {
    const hits = await api('/api/complaints?' + new URLSearchParams({ q, limit: 12, ...(cat && { category: cat }) }));
    box.hidden = false;
    box.innerHTML = `<h3>Matching complaints (BM25 ranked)</h3>` + (hits.map((c) => feedItem(c)).join('') || '<div class="muted">No matching complaints.</div>');
  } else box.hidden = true;
}

export async function openIssue(id) {
  const d = await api('/api/issues/' + id);
  $('#drawerBody').innerHTML = `<h2 style="font-size:18px;margin:4px 40px 6px 0">${catDot(d.category)}${esc(d.title)}</h2>
    <div class="row" style="margin:6px 0 14px">${sevPill(lvl(d.avg_severity), d.avg_severity)} <span class="tag">${d.count} complaints</span> <span class="tag">${d.recent} in last hour</span> <span class="tag">${esc(d.mode)}</span></div>
    <div class="card" style="background:var(--surface-2)"><dl class="kv">
      <dt>First seen</dt><dd>${fmtDay(d.first_seen)}</dd><dt>Last seen</dt><dd>${ago(d.last_seen)}</dd>
      <dt>Places</dt><dd>${esc(d.locations.join(', ') || '—')}</dd><dt>Routes</dt><dd>${esc(d.routes.join(', ') || '—')}</dd>
      <dt>Key phrases</dt><dd>${esc(d.keywords.join(' · ') || '—')}</dd><dt>Peak severity</dt><dd>${d.max_severity}</dd>
      <dt>Last 2 hours</dt><dd>${spark(d.spark, S.colors[d.category], 160, 28)}</dd>
      <dt>Sources</dt><dd>${Object.entries(d.sources).map(([k, v]) => `${esc(k)} ${v}`).join(' · ')}</dd></dl></div>
    <h3 style="margin-top:16px">Recent complaints in this issue</h3><div class="list">${d.complaints.map((c) => feedItem(c)).join('')}</div>`;
  $('#drawer').classList.add('open'); $('#drawer').setAttribute('aria-hidden', 'false');
}
export function closeDrawer() { $('#drawer').classList.remove('open'); $('#drawer').setAttribute('aria-hidden', 'true'); }
