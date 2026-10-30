import { $, S, api, esc, sevPill, catDot, catName, toast } from './core.js';

const EXAMPLES = [
  'Bus 335E broke dwn near Silk Bord, stuck for 45 mins, women and kids stranded. pls help!!',
  'AC not working in 500D since 2 weeks, sooo hot and dirty seats #BMTC',
  'bahut bheed hai Majestic pe, ek bhi bus nahi ruki. conductor ne gaali di',
  'metro purple line delayed again 20 mins at Indiranagar, office meeting missed',
  'Man harassing girls near Hebbal bus stop at night, no lights, no security',
  'UPI payment failed but money deducted, conductor gave no ticket on 356',
  'Thanks to the driver of 335E who waited for me, really kind',
];
const TAG_COLORS = { NOUN: '#3987e5', VERB: '#d95926', ADJ: '#c98500', ADV: '#9085e9', NUM: '#199e70', PROPN: '#d55181', ADP: '#7a8799', DET: '#7a8799', AUX: '#7a8799', PRON: '#7a8799', CONJ: '#7a8799', PART: '#e66767' };
const lvl = (v) => (v >= 78 ? 'critical' : v >= 55 ? 'high' : v >= 30 ? 'medium' : 'low');

export function initAnalyzer() {
  $('#azExamples').innerHTML = EXAMPLES.map((e, i) => `<span class="chip" data-i="${i}">${esc(e.slice(0, 44))}…</span>`).join('');
  $('#azExamples').onclick = (e) => { const c = e.target.closest('.chip'); if (c) { $('#azText').value = EXAMPLES[+c.dataset.i]; run(); } };
  $('#azRun').onclick = run;
  $('#azText').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run(); });
  $('#azSend').onclick = async () => {
    const text = $('#azText').value.trim(); if (!text) return;
    const c = await api('/api/complaints', { method: 'POST', body: { text, source: 'Manual Entry' } });
    $('#azStatus').textContent = `Added to live stream as ${c.category_label} (severity ${Math.round(c.severity)}).`;
  };
  $('#azCsv').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    try { const r = await api('/api/complaints/batch', { method: 'POST', body: fd }); $('#azStatus').textContent = `Ingested ${r.ingested} complaints from CSV.`; }
    catch (err) { $('#azStatus').textContent = 'Upload failed: ' + err.message; }
    e.target.value = '';
  };
  document.addEventListener('analyze-text', (e) => { document.querySelector('[data-page=analyzer]').click(); $('#azText').value = e.detail; run(); });
}

async function run() {
  const text = $('#azText').value.trim(); if (!text) return;
  $('#azStatus').textContent = 'Analyzing…';
  try { render(await api('/api/analyze', { method: 'POST', body: { text } })); $('#azStatus').textContent = ''; }
  catch (e) { $('#azStatus').textContent = 'Error: ' + e.message; }
}

function render(r) {
  const fixed = new Map(r.corrections.map((c) => [c.index, c]));
  const toks = r.tokens.map((t, i) => fixed.has(i) ? `<span class="tok fixed" title="edit distance ${fixed.get(i).distance}"><s>${esc(fixed.get(i).from)}</s>${esc(t)}</span>` : `<span class="tok">${esc(t)}</span>`).join('');
  const pos = r.trace.pos.map((p) => `<span class="tok" style="border-bottom:2px solid ${TAG_COLORS[p.tag] || '#7a8799'}" title="${p.by}">${esc(p.token)}<sub>${p.tag}</sub></span>`).join('');
  const probs = Object.entries(r.probs).slice(0, 6).map(([c, p]) => `<div class="pbar"><span>${catDot(c)}${esc(catName(c))}</span><div class="tr"><i style="width:${p * 100}%;background:${S.colors[c]}"></i></div><b>${(p * 100).toFixed(1)}%</b></div>`).join('');
  const facs = r.severity_factors.map((f) => `<div class="fac"><span>${esc(f.label)}</span><b>+${f.points}</b></div>`).join('');
  const locs = r.locations.length ? r.locations.map((l) => `<span class="tag">📍 ${esc(l.name)} <span class="muted">${l.type}${l.fuzzy ? ' · fuzzy' : ''}</span></span>`).join(' ') : '<span class="muted">none found</span>';
  const rel = r.trace.related_terms.map((t) => `<div><b>${esc(t.term)}</b> <span class="muted">≈ ${t.neighbours.map((n) => esc(n.term)).join(', ')}</span></div>`).join('') || '<span class="muted">—</span>';
  $('#azResult').hidden = false;
  $('#azResult').innerHTML = `
  <div class="card wide"><h3>1 · Normalisation &amp; spelling correction <span class="muted" style="text-transform:none">(min edit distance + n-gram LM)</span></h3>
    <div class="muted" style="margin-bottom:6px">Raw: ${esc(r.raw)}</div><div>${toks}</div>
    ${r.corrections.length ? `<div class="muted" style="margin-top:8px">${r.corrections.map((c) => `<code>${esc(c.from)}</code> → <code>${esc(c.to)}</code> (distance ${c.distance}: ${c.ops.map((o) => o.op === 'match' ? o.a : o.op === 'sub' ? `<b>${o.a}→${o.b}</b>` : o.op === 'del' ? `<b>−${o.a}</b>` : `<b>+${o.b}</b>`).join('')})`).join(' &nbsp;·&nbsp; ')}</div>` : ''}
    ${r.code_mixed.length ? `<div style="margin-top:8px"><span class="tag">Code-mixed: ${r.code_mixed.map((x) => x === 'hi' ? 'Hindi (romanised)' : 'Kannada (romanised)').join(' + ')}</span> <span class="muted">${r.trace.code_mix_hits.map((h) => esc(h.token) + '=' + esc(h.gloss)).join(', ')}</span></div>` : ''}</div>
  <div class="card"><h3>2 · Part-of-speech &amp; key phrases</h3><div>${pos}</div><div style="margin-top:8px"><span class="muted">Issue phrases:</span> ${r.phrases.map((p) => `<span class="tag">${esc(p)}</span>`).join(' ') || '—'}</div></div>
  <div class="card"><h3>3 · Entities</h3><dl class="kv"><dt>Locations</dt><dd>${locs}</dd><dt>Primary</dt><dd>${esc(r.location || '—')}${r.lat ? ` <span class="muted">(${r.lat.toFixed(3)}, ${r.lng.toFixed(3)})</span>` : ''}</dd>
    <dt>Route / line</dt><dd>${esc(r.route || '—')}</dd><dt>Mode</dt><dd>${esc(r.mode)}</dd></dl><h3 style="margin-top:14px">Related terms (LSA semantic space)</h3>${rel}</div>
  <div class="card"><h3>4 · Classification <span class="muted" style="text-transform:none">(TF-IDF + logistic regression)</span></h3>
    <div style="margin-bottom:8px">${catDot(r.category)}<b style="font-size:16px">${esc(r.category_label)}</b> <span class="muted">· confidence ${(r.confidence * 100).toFixed(1)}%</span> ${r.low_confidence ? '<span class="tag">low confidence · needs review</span>' : ''}</div>${probs}</div>
  <div class="card"><h3>5 · Severity <span class="muted" style="text-transform:none">(explainable score)</span></h3>
    <div class="row" style="margin:0"><span class="big">${Math.round(r.severity)}</span>${sevPill(r.severity_level, r.severity)}</div>
    <div class="gauge"><i style="left:${r.severity}%"></i></div>${facs}</div>
  <div class="card wide muted">Processed in ${r.latency_ms} ms.</div>`;
}
