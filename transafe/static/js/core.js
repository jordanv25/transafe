// Shared helpers and global state
export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export async function api(path, opts = {}) {
  const o = { headers: {}, ...opts };
  if (o.body && !(o.body instanceof FormData)) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(o.body); }
  const r = await fetch(path, o);
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
}

export const S = { meta: null, snap: null, feed: [], filter: '', cats: {}, colors: {}, labels: {} };

export const fmtClock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
export const fmtDay = (ts) => new Date(ts * 1000).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
export function ago(ts) {
  const now = S.snap ? S.snap.now : Date.now() / 1000;
  const s = Math.max(0, now - ts);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + ' min ago';
  if (s < 86400) return Math.floor(s / 3600) + ' h ago';
  return Math.floor(s / 86400) + ' d ago';
}
export const sevPill = (level, score) => `<span class="pill ${level}" title="Severity score ${score}/100">${level} · ${Math.round(score)}</span>`;
export const catDot = (c) => `<i class="dot" style="background:${S.colors[c] || '#888'}"></i>`;
export const catName = (c) => S.labels[c] || c;

export function spark(vals, color = '#4cc9f0', w = 80, h = 22) {
  const max = Math.max(1, ...vals), step = w / Math.max(1, vals.length - 1);
  const pts = vals.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - (v / max) * (h - 4)).toFixed(1)}`).join(' ');
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" points="${pts}"/></svg>`;
}

export function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.innerHTML = msg;
  $('#toasts').appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

export function feedItem(c, isNew = false) {
  const fix = c.corrections && c.corrections.length ? `<span class="fix" title="Spelling corrected by edit-distance noisy-channel model">✎ ${c.corrections.slice(0, 2).map((x) => esc(x.from) + '→' + esc(x.to)).join(', ')}</span>` : '';
  const code = c.code_mixed && c.code_mixed.length ? `<span class="tag">${c.code_mixed.join('+').replace('hi', 'Hinglish').replace('kn', 'Kanglish')}</span>` : '';
  const meta = [c.location ? '📍 ' + esc(c.location) : '', c.route ? '🚌 ' + esc(c.route) : '', esc(c.source)].filter(Boolean).join(' · ');
  const sev = c.actionable ? sevPill(c.severity_level, c.severity) : '<span class="pill">not a complaint</span>';
  return `<div class="fi ${isNew ? 'new' : ''} ${c.actionable ? '' : 'irrelevant'}" style="--c:${c.color}" data-text="${esc(c.raw)}">
    <div class="hd"><b>${esc(c.category_label)}</b><span>${Math.round(c.confidence * 100)}%</span>${sev}${code}<span style="margin-left:auto">${ago(c.ts)}</span></div>
    <div class="tx">${esc(c.raw)}</div><div class="ft"><span>${meta}</span>${fix}</div></div>`;
}
