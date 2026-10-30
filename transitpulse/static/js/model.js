import { $, S, api, esc, catName } from './core.js';

const pct = (x) => (x * 100).toFixed(1) + '%';
const short = (c) => ({ overcrowding: 'Crowd', delay: 'Delay', safety: 'Safety', driver_behavior: 'Driver', vehicle_condition: 'Vehicle', fare_ticketing: 'Fare', breakdown: 'Breakdown', accessibility: 'Access', other: 'Other' }[c]);

function cm(rep, classes) {
  const mx = Math.max(...rep.confusion.flat(), 1);
  const rows = rep.confusion.map((r, i) => {
    const tot = r.reduce((a, b) => a + b, 0) || 1;
    return `<tr><th style="text-align:right">${short(classes[i])}</th>${r.map((v, j) => `<td title="true ${classes[i]} → predicted ${classes[j]}: ${v}" style="background:rgba(57,135,229,${(v / tot).toFixed(2)});color:${v / tot > .5 ? '#fff' : '#aab5c4'}">${v || ''}</td>`).join('')}</tr>`;
  }).join('');
  return `<div class="cm-wrap"><table class="cm"><tr><th></th>${classes.map((c) => `<th>${short(c)}</th>`).join('')}</tr>${rows}</table></div><div class="muted" style="margin-top:4px">rows = true class · columns = predicted</div>`;
}

export async function loadModel() {
  const m = await api('/api/model');
  if (!m.gold_lr) { $('#modelRoot').innerHTML = '<div class="card">No metrics yet - run <code>python run.py --retrain</code>.</div>'; return; }
  const cls = m.dataset.classes, g = m.gold_lr;
  const rowsPC = cls.map((c) => { const p = g.per_class[c]; return `<tr><td>${esc(catName(c))}</td><td class="num">${pct(p.precision)}</td><td class="num">${pct(p.recall)}</td><td class="num"><b>${pct(p.f1)}</b></td><td class="num">${p.support}</td></tr>`; }).join('');
  const lm = m.language_model.map((r) => `<tr><td>${r.model}</td><td class="num">${r.ppl_heldout ?? '∞'}</td><td class="num">${r.ppl_gold ?? '∞'}</td></tr>`).join('');
  $('#modelRoot').innerHTML = `
  <div class="stat-row">
    <div class="kpi"><div class="v">${pct(g.accuracy)}</div><div class="l">Accuracy · hand-written test set</div><div class="s">${g.n} unseen complaints, never trained on</div></div>
    <div class="kpi"><div class="v">${pct(g.macro_f1)}</div><div class="l">Macro-F1 · hand-written test set</div><div class="s">average over 9 classes</div></div>
    <div class="kpi"><div class="v">${pct(m.template_holdout.accuracy)}</div><div class="l">Accuracy · unseen templates</div><div class="s">${m.template_holdout.n} synthetic, held-out phrasings</div></div>
    <div class="kpi"><div class="v">${m.dataset.train_examples.toLocaleString()}</div><div class="l">Training examples</div><div class="s">${m.dataset.templates} phrase templates, with noise</div></div>
  </div>
  <div class="card" style="margin-bottom:14px"><h2>Processing pipeline <small>every stage is implemented in this project</small></h2><div class="pipeline" style="margin-top:10px">
    <div class="stage"><b>1 Normalise</b><span>unicode, hashtags, slang, Hinglish/Kanglish lexicon</span><br><em>Unit I</em></div>
    <div class="stage"><b>2 Spell-correct</b><span>min edit distance + Kneser-Ney bigram LM (noisy channel)</span><br><em>Units II, III</em></div>
    <div class="stage"><b>3 POS tag</b><span>lexicon + suffix + Brill transformation rules</span><br><em>Unit II</em></div>
    <div class="stage"><b>4 Classify</b><span>TF-IDF word+char n-grams → logistic regression</span><br><em>Unit I, V</em></div>
    <div class="stage"><b>5 Extract</b><span>gazetteer NER with fuzzy matching; routes, mode</span><br><em>Unit I</em></div>
    <div class="stage"><b>6 Severity</b><span>explainable lexical + numeric scoring, negation</span><br><em>Unit I</em></div>
    <div class="stage"><b>7 Cluster</b><span>LSA distributional vectors + place + route</span><br><em>Unit V</em></div>
    <div class="stage"><b>8 Trend</b><span>Poisson z-score burst detection; BM25 search</span><br><em>Unit V</em></div></div></div>
  <div class="az-grid">
    <div class="card"><h3>Per-class results · hand-written test set</h3><div class="table-wrap"><table class="tbl"><thead><tr><th>Class</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th class="num">n</th></tr></thead><tbody>${rowsPC}</tbody></table></div></div>
    <div class="card"><h3>Confusion matrix · hand-written test set</h3>${cm(g, cls)}</div>
    <div class="card"><h3>Classifier comparison</h3><table class="tbl"><thead><tr><th>Evaluation</th><th class="num">Accuracy</th><th class="num">Macro-F1</th></tr></thead><tbody>
      <tr><td>Logistic regression · hand-written test</td><td class="num"><b>${pct(m.gold_lr.accuracy)}</b></td><td class="num">${pct(m.gold_lr.macro_f1)}</td></tr>
      <tr><td>Naive Bayes baseline · hand-written test</td><td class="num">${pct(m.gold_nb.accuracy)}</td><td class="num">${pct(m.gold_nb.macro_f1)}</td></tr>
      <tr><td>Logistic regression · unseen templates</td><td class="num">${pct(m.template_holdout.accuracy)}</td><td class="num">${pct(m.template_holdout.macro_f1)}</td></tr>
      <tr><td>Logistic regression · random split*</td><td class="num">${pct(m.random_split.accuracy)}</td><td class="num">${pct(m.random_split.macro_f1)}</td></tr></tbody></table>
      <p class="muted">*Random split shares phrase templates between train and test, so it is optimistic. The hand-written set is the honest number. Training data is synthetic (generated from templates), so real-world accuracy needs validation on real complaints.</p></div>
    <div class="card"><h3>Language-model smoothing · perplexity (lower is better)</h3><table class="tbl"><thead><tr><th>Model</th><th class="num">Held-out</th><th class="num">Hand-written</th></tr></thead><tbody>${lm}</tbody></table>
      <p class="muted">Without smoothing an unseen bigram gets probability 0 (perplexity ∞). Kneser-Ney wins in-domain (held-out). The hand-written set is out-of-domain with many unseen words and word pairs, so every model degrades, and add-1 can score better there simply because it hands more probability mass to unseen events.</p></div>
  </div>`;
}
