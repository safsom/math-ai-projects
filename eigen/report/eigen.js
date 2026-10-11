const $ = (s) => document.querySelector(s);
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const fmt = (x, d = 2) => (x == null || Number.isNaN(x)) ? '–' : Number(x).toFixed(d);
const pct = (x, d = 0) => (x == null || Number.isNaN(x)) ? '–' : (100 * x).toFixed(d) + '%';
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const GCOL = { mathlib: 'var(--c-mathlib)', openai: 'var(--c-openai)', human: 'var(--c-human)', 'human-upstream': 'var(--c-human)' };
const GNAME = { mathlib: 'mathlib (held out)', openai: 'OpenAI math', human: 'Human research', 'human-upstream': 'Human, upstreaming dirs' };

function ticks(lo, hi, n = 6) {
  const span = hi - lo, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}
function tipper(chart) {
  const tip = chart.querySelector('.tip');
  return {
    show(evt, html) {
      tip.innerHTML = html; tip.style.display = 'block';
      const r = chart.getBoundingClientRect();
      let x = evt.clientX - r.left + 12, y = evt.clientY - r.top + 12;
      if (x + 300 > r.width) x = Math.max(4, evt.clientX - r.left - 300);
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    },
    hide() { tip.style.display = 'none'; },
  };
}
function hash(s) { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return ((h >>> 0) % 1000) / 1000; }

// ---------- text ----------
for (const k of ['lede', 'types-text', 'ir-text', 'lin-text', 'spec-text', 'ep-text', 'nm-text', 'ou-text', 'old-text', 'method', 'example-cap', 'sc-cap', 'cut-text', 'cut-cap', 'rc-text', 'rc-table', 'rc-table2', 'rc-cap', 'ai-text', 'ai-cap']) {
  const node = document.getElementById(k);
  if (node && DATA.text[k] != null) node.innerHTML = DATA.text[k];
}
if (!DATA.text['rc-text']) { const s = $('#rc-section'); if (s) s.remove(); }
$('#figs').innerHTML = DATA.figs.map((f) => `<div class="fig"><div class="v">${f.v}${f.unit ? ` <small>${f.unit}</small>` : ''}</div><div class="l">${f.l}</div></div>`).join('');

// ---------- worked example ----------
(function () {
  const parts = [];
  for (const ex of DATA.example) {
    const tree = ex.tree.map(([d, g, desc]) => {
      const m = g.match(/^(λh:|λx:|cut:)(.*?)(?::([01ω]))?$/);
      let label;
      if (m) {
        label = `<span class="mech">${esc(m[1].replace(':', ''))}</span>${m[2] ? ` <span class="ty">${esc(m[2])}</span>` : ''}${m[3] ? ` <span class="lin">use ${m[3]}</span>` : ''}`;
      } else {
        const a = g.match(/^([^()]*)\((.*)\)⇒(.*)$/);
        label = a ? `<span class="mech">${esc(a[1])}</span><span class="rule">(</span><span class="ty">${esc(a[2])}</span><span class="rule">)⇒</span><span class="ty">${esc(a[3])}</span>` : esc(g);
      }
      return `${'  '.repeat(d)}<span class="rule">${d ? '└ ' : ''}</span>${label}${desc ? `  <span class="rule">— ${esc(desc)}</span>` : ''}`;
    }).join('\n');
    parts.push(`<div class="pane"><header><span><b>${esc(ex.label)}</b> · <span class="mono">${esc(ex.name)}</span></span><span class="meta">source</span></header><pre>${esc(ex.src)}</pre></div>`);
    parts.push(`<div class="pane"><header><span>${esc(ex.label)}: gestures read off the elaborated term</span><span class="meta">${ex.tree.length} steps</span></header><div class="tree">${tree}</div></div>`);
  }
  $('#example').innerHTML = parts.join('');
})();

// ---------- strip ----------
(function drawStrip() {
  const svg = $('#ir-strip');
  const groups = ['mathlib', 'openai', 'human', 'human-upstream'].filter((g) => DATA.projects.some((p) => p.group === g));
  const W = 940, L = 190, R = 20, T = 10, B = 34, rowH = 52;
  const H = T + rowH * groups.length + B;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const vals = DATA.projects.map((p) => p.e_ir).sort((a, b) => a - b);
  const lo = Math.floor(vals[0] * 2) / 2, hi = Math.ceil(vals[vals.length - 1] * 2) / 2;
  const x = (v) => L + (v - lo) / (hi - lo) * (W - L - R);
  for (const t of ticks(lo, hi)) {
    el('line', { x1: x(t), x2: x(t), y1: T, y2: H - B, class: 'gridline' }, svg);
    el('text', { x: x(t), y: H - B + 18, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = t;
  }
  $('#ir-legend').innerHTML = `<span><i style="background:var(--c-mathlib)"></i>mathlib</span><span><i style="background:var(--c-openai)"></i>OpenAI</span><span><i style="background:var(--c-human)"></i>Human (Carleson, sphere eversion)</span><span>│ median with 95% interval</span>`;
  const tp = tipper($('#ir-chart'));
  groups.forEach((g, i) => {
    const cy = T + rowH * (i + 0.5);
    const ps = DATA.projects.filter((p) => p.group === g);
    el('text', { x: 0, y: cy - 2, 'dominant-baseline': 'middle' }, svg).textContent = GNAME[g];
    el('text', { x: 0, y: cy + 13, 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = `${ps.length} project${ps.length === 1 ? '' : 's'}`;
    for (const p of ps) {
      const c = el('circle', { cx: x(p.e_ir), cy: cy + (hash(p.project) - 0.5) * rowH * 0.6, r: ps.length > 100 ? 3 : 4.5,
        fill: GCOL[g], stroke: 'var(--panel)', 'stroke-width': 0.75, 'fill-opacity': 0.75 }, svg);
      c.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">${GNAME[g]}</div><b>${esc(p.project)}</b><br>${fmt(p.e_ir)} bits per step · ${p.n} theorems`));
      c.addEventListener('mouseleave', tp.hide);
    }
    const gm = DATA.groups.find((r) => r.group === g && r.metric === 'e_ir');
    if (gm && gm.lo != null) {
      el('line', { x1: x(gm.lo), x2: x(gm.hi), y1: cy, y2: cy, stroke: 'var(--ink)', 'stroke-width': 3, 'stroke-linecap': 'round' }, svg);
      el('line', { x1: x(gm.median), x2: x(gm.median), y1: cy - rowH * 0.36, y2: cy + rowH * 0.36, stroke: 'var(--ink)', 'stroke-width': 2 }, svg);
      el('text', { x: x(gm.median) + 6, y: cy - rowH * 0.26, style: 'fill:var(--ink);font-weight:600' }, svg).textContent = fmt(gm.median);
    }
  });
})();

// ---------- scatter ----------
(function drawScatter() {
  const svg = $('#scatter');
  const ps = DATA.projects.filter((p) => p.e_tok != null);
  const W = 940, H = 420, L = 56, R = 20, T = 14, B = 44;
  const xs = ps.map((p) => p.e_ir), ys = ps.map((p) => p.e_tok);
  const x0 = Math.floor(Math.min(...xs) * 2) / 2, x1 = Math.ceil(Math.max(...xs) * 2) / 2;
  const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys));
  const x = (v) => L + (v - x0) / (x1 - x0) * (W - L - R);
  const y = (v) => H - B - (v - y0) / (y1 - y0) * (H - T - B);
  for (const t of ticks(x0, x1)) {
    el('line', { x1: x(t), x2: x(t), y1: T, y2: H - B, class: 'gridline' }, svg);
    el('text', { x: x(t), y: H - B + 18, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = t;
  }
  for (const t of ticks(y0, y1)) {
    el('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), class: 'gridline' }, svg);
    el('text', { x: L - 8, y: y(t), 'text-anchor': 'end', 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = t;
  }
  el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle' }, svg).textContent = 'compiled energy, bits per inference step (names erased)';
  const yl = el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', transform: `rotate(-90 14 ${(T + H - B) / 2})` }, svg);
  yl.textContent = 'text energy, bits per token';
  const tp = tipper($('#sc-chart'));
  const order = ['mathlib', 'human-upstream', 'human', 'openai'];
  for (const g of order) {
    for (const p of ps.filter((q) => q.group === g)) {
      const c = el('circle', { cx: x(p.e_ir), cy: y(p.e_tok), r: g === 'mathlib' ? 3 : 4.5, fill: GCOL[g],
        'fill-opacity': g === 'mathlib' ? 0.45 : 0.85, stroke: 'var(--panel)', 'stroke-width': 0.75 }, svg);
      c.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">${GNAME[g]}</div><b>${esc(p.project)}</b><br>compiled ${fmt(p.e_ir)} · text ${fmt(p.e_tok)} bits`));
      c.addEventListener('mouseleave', tp.hide);
    }
  }
})();

// ---------- structural rules table ----------
(function () {
  const ms = ['weakening', 'linear', 'contraction', 'cuts_per_100', 'single_use_cut', 'dead_cut', 'nodes_med'];
  const groups = ['mathlib', 'openai', 'human', 'human-upstream'];
  let h = `<thead><tr><th>Median project [95% interval]</th>${groups.map((g) => `<th>${GNAME[g]}</th>`).join('')}</tr></thead><tbody>`;
  for (const m of ms) {
    const lab = DATA.groups.find((r) => r.metric === m);
    if (!lab) continue;
    h += `<tr><td>${lab.label}<br><span class="cap">${lab.definition}</span></td>`;
    for (const g of groups) {
      const r = DATA.groups.find((x) => x.metric === m && x.group === g);
      const isShare = !['cuts_per_100', 'nodes_med'].includes(m);
      const f = (v) => v == null ? '–' : isShare ? pct(v, 1) : fmt(v, 1);
      h += `<td>${f(r && r.median)}<br><span class="cap">${r && r.lo != null ? `${f(r.lo)}–${f(r.hi)}` : ''}</span></td>`;
    }
    h += '</tr>';
  }
  $('#lin-table').innerHTML = h + `</tbody><tfoot><tr><td class="cap">Projects</td>${groups.map((g) => `<td class="cap">${(DATA.groups.find((x) => x.group === g) || {}).n || 0}</td>`).join('')}</tr></tfoot>`;
})();

// ---------- spectrum ----------
(function drawSpectrum() {
  const svg = $('#spectrum');
  const n = 20;
  const oa = DATA.spectrum.openai.slice(0, n), hu = DATA.spectrum.human.slice(0, n);
  const nullMed = DATA.null.top_median, nullMax = DATA.null.top_max;
  const W = 940, H = 300, L = 56, R = 16, T = 12, B = 40;
  const ymax = Math.max(...oa.map((r) => r.bits), ...hu.map((r) => r.bits), ...nullMax) * 1.05;
  const bw = (W - L - R) / n;
  const x = (i) => L + i * bw;
  const y = (v) => H - B - v / ymax * (H - T - B);
  for (const t of ticks(0, ymax, 5)) {
    el('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), class: 'gridline' }, svg);
    el('text', { x: L - 8, y: y(t), 'text-anchor': 'end', 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = t;
  }
  const tp = tipper($('#spec-chart'));
  for (let i = 0; i < n; i++) {
    if (i < nullMax.length) {
      el('rect', { x: x(i) + 2, y: y(nullMax[i]), width: bw - 4, height: y(0) - y(nullMax[i]), fill: 'var(--grid)', stroke: 'var(--rule)' }, svg);
    }
    const o = oa[i], h = hu[i];
    const ro = el('rect', { x: x(i) + bw * 0.16, y: y(o.bits), width: bw * 0.38, height: Math.max(0, y(0) - y(o.bits)), fill: 'var(--c-openai)', rx: 2 }, svg);
    ro.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">Eigenproof ${i + 1}, OpenAI vs mathlib</div><b>${fmt(o.bits, 1)} bits</b><br>variance ratio λ = ${fmt(o.lam)} · mean shift ${fmt(o.shift)} mathlib SD`));
    ro.addEventListener('mouseleave', tp.hide);
    if (h) {
      const rh = el('rect', { x: x(i) + bw * 0.56, y: y(h.bits), width: bw * 0.26, height: Math.max(0, y(0) - y(h.bits)), fill: 'var(--c-human)', rx: 2 }, svg);
      rh.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">Rank ${i + 1}, human research vs mathlib</div><b>${fmt(h.bits, 1)} bits</b>`));
      rh.addEventListener('mouseleave', tp.hide);
    }
    el('text', { x: x(i) + bw / 2, y: H - B + 16, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = i + 1;
  }
  el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle' }, svg).textContent = 'eigenproof rank';
})();

// ---------- eigenproof cards ----------
(function () {
  const cards = DATA.modes.map((m, i) => {
    const maxL = Math.max(...m.pos.map((p) => Math.abs(p.loading)), ...m.neg.map((p) => Math.abs(p.loading)));
    const row = (p, col) => `<div class="lrow"><div class="lbar" style="width:${Math.max(4, 64 * Math.abs(p.loading) / maxL)}px;background:${col}"></div><div>${esc(p.desc)}<span class="g">${esc(p.gesture)}</span></div></div>`;
    const prevRow = (g) => {
      const v = m.prevalence[g];
      if (!v) return '';
      return `<div class="bar"><span>${GNAME[g]}</span><div class="track"><div class="fill" style="width:${Math.min(100, 100 * v.beyond2 / Math.max(0.0001, Math.max(...Object.values(m.prevalence).map((q) => q.beyond2))))}%;background:${GCOL[g]}"></div></div><span class="num">${pct(v.beyond2, 1)}</span></div>`;
    };
    const exBlock = (arr, who) => arr.map((x) => `<div class="pane"><header><span><b>${who}</b> · <span class="mono">${esc(x.name)}</span></span><span class="meta">${esc(x.project)} · score ${fmt(x.score, 1)}</span></header><pre>${esc(x.text)}</pre></div>`).join('');
    return `<article class="ep">
      <div class="ep-head"><div><div class="k">Eigenproof ${m.rank}</div><h3>${esc(m.title || '')}</h3></div>
        <div class="chips"><span class="chip">carries <b>${fmt(m.bits, 1)}</b> bits</span><span class="chip">variance ratio λ <b>${fmt(m.lam)}</b></span><span class="chip">mean shift <b>${fmt(m.shift)}</b> SD</span>${DATA.stability ? `<span class="chip">split-half match <b>${fmt(DATA.stability[i])}</b></span>` : ''}</div></div>
      ${m.blurb ? `<p class="small">${m.blurb}</p>` : ''}
      <div class="loads"><div><h4>More of</h4>${m.pos.slice(0, 6).map((p) => row(p, 'var(--pos)')).join('')}</div><div><h4>Less of</h4>${m.neg.slice(0, 5).map((p) => row(p, 'var(--neg)')).join('')}</div></div>
      <div class="prev"><h4 class="cap" style="margin:0">Share of theorems beyond +2 mathlib SD on this eigenproof</h4>${prevRow('mathlib')}${prevRow('openai')}${prevRow('human')}</div>
      <div class="ex">${exBlock(m.ex_openai.slice(0, 1), 'OpenAI')}
        <details class="ex-more"><summary>More examples</summary><div class="ex" style="margin-top:8px">${exBlock(m.ex_openai.slice(1), 'OpenAI')}${exBlock(m.ex_mathlib, 'mathlib')}${exBlock(m.ex_human, 'Human')}</div></details></div>
    </article>`;
  });
  $('#eps').innerHTML = cards.join('');
})();

// ---------- normal modes ----------
(function () {
  let h = `<thead><tr><th>mathlib mode</th><th>Variance share</th><th>Mostly</th><th>Against</th><th>OpenAI mean shift</th><th>OpenAI variance ratio</th></tr></thead><tbody>`;
  for (const m of DATA.normal) {
    h += `<tr><td>${m.rank}</td><td>${pct(m.var_share, 1)}</td><td style="white-space:normal">${m.pos.slice(0, 3).map((p) => esc(p.desc)).join('<br>')}</td><td style="white-space:normal">${m.neg.slice(0, 2).map((p) => esc(p.desc)).join('<br>')}</td><td>${fmt(m.openai_shift)} SD</td><td>${fmt(m.openai_var_ratio)}</td></tr>`;
  }
  $('#nm-table').innerHTML = h + '</tbody>';
})();

// ---------- over / under ----------
(function () {
  const t = (rows, title) => `<thead><tr><th>${title}</th><th>OpenAI</th><th>mathlib</th><th>Human</th><th>Ratio</th></tr></thead><tbody>${rows.map((r) => `<tr><td style="white-space:normal">${esc(r.desc)}<br><span class="cap mono">${esc(r.gesture)}</span></td><td>${pct(r.openai, 2)}</td><td>${pct(r.mathlib, 2)}</td><td>${pct(r.human, 2)}</td><td>${(2 ** r.log2_ratio).toFixed(r.log2_ratio > 0 ? 1 : 2)}×</td></tr>`).join('')}</tbody>`;
  $('#over-table').innerHTML = t(DATA.over, 'Used more by OpenAI');
  $('#under-table').innerHTML = t(DATA.under, 'Used less by OpenAI');
})();

// ---------- old attributes ----------
(function () {
  const cols = DATA.old_cols;
  let h = `<thead><tr><th>Eigenproof</th>${cols.map((c) => `<th style="white-space:normal">${esc(c[1])}</th>`).join('')}</tr></thead><tbody>`;
  for (const [k, row] of Object.entries(DATA.old_corr)) {
    h += `<tr><td>${k.replace('ep', 'Eigenproof ')}</td>${cols.map(([c]) => {
      const v = row[c];
      if (!v) return '<td>–</td>';
      const strong = Math.abs(v.rho) >= 0.3 && v.q < 0.05;
      return `<td class="rho" style="${strong ? 'font-weight:600;color:var(--ink)' : 'color:var(--ink-3)'}">${v.rho >= 0 ? '+' : ''}${v.rho.toFixed(2)}</td>`;
    }).join('')}</tr>`;
  }
  $('#old-table').innerHTML = h + '</tbody>';
})();

// ---------- cut compression ----------
(function () {
  const C = DATA.cuts;
  if (!C) { const s = $('#cut-section'); if (s) s.remove(); return; }
  const cols = C.columns;
  const row = (label, def, f) => `<tr><td>${label}<br><span class="cap">${def}</span></td>${cols.map((c) => `<td>${f(c)}</td>`).join('')}</tr>`;
  const pp = (c) => C.per_proof[c.key] || {}, po = (c) => C.pooled[c.key] || {}, pm = (c) => C.project_median[c.key] || {};
  const b = (x) => x == null ? '–' : (x >= 0 ? '' : '−') + Math.abs(x).toFixed(3);
  let h = `<thead><tr><th>Per proof (theorems with at least 10 steps)</th>${cols.map((c) => `<th style="white-space:normal">${esc(c.name)}</th>`).join('')}</tr></thead><tbody>`;
  h += row('Proofs', 'theorems measured', (c) => (po(c).proofs || 0).toLocaleString());
  h += row('Proofs with a cut', 'have, let or β-redex of a proof', (c) => pct(pp(c).with_cut, 1));
  h += row('Cuts per 100 steps', 'all cuts, by the size of the proof as written', (c) => fmt(po(c).cuts_per_100, 2));
  h += row('Dead · linear · shared', 'share of cuts used 0, 1 or ≥2 times', (c) => po(c).share ? `${pct(po(c).share.dead, 0)} · ${pct(po(c).share.linear, 0)} · ${pct(po(c).share.shared, 0)}` : '–');
  h += row('κ, compression', 'bits: log₂(cut-free size ÷ size as written), mean per proof', (c) => b(po(c).kappa_mean));
  h += row('χ, compressibility', 'bits: log₂(cut-free ÷ optimal), mean per proof', (c) => b(po(c).chi_mean));
  h += row('ρ, layout redundancy', 'bits: log₂(as written ÷ optimal), mean per proof', (c) => b(po(c).rho_mean));
  h += row('Proofs at least doubling', 'share whose cut-free form is ≥2× the optimal (χ ≥ 1)', (c) => pct(po(c).chi_ge1, 1));
  h += row('Proofs whose cuts cost more than they save', 'share with κ < 0', (c) => pct(po(c).kappa_neg, 1));
  h += row('σ · ℓ · w, size-weighted', 'bits: sharing gain · linear overhead · dead overhead', (c) => po(c).sigma == null ? '–' : `${po(c).sigma.toFixed(3)} · ${po(c).l.toFixed(3)} · ${po(c).w.toFixed(3)}`);
  h += `<tr><td colspan="${cols.length + 1}" class="cap" style="padding-top:var(--s-3)"><b>Per project, lemmas as cuts</b> (median project with at least 20 proofs)</td></tr>`;
  h += row('Lemma-level κ', 'bits: log₂(project with every local lemma inlined ÷ project as written)', (c) => b(pm(c).kappa_lemma));
  h += row('Reused lemmas', 'share of local theorems cited ≥2 times inside their project', (c) => pct(pm(c).lemma_shared_frac, 0));
  h += row('Single-use lemmas', 'share of local theorems cited exactly once', (c) => pct(pm(c).lemma_linear_frac, 0));
  h += row('Projects', 'with at least 20 measured proofs', (c) => pm(c).projects == null ? '–' : pm(c).projects);
  $('#cut-table').innerHTML = h + '</tbody>';
})();

// ---------- other AI corpora ----------
(function () {
  const A = DATA.ai;
  if (!A) { const s = $('#ai-section'); if (s) s.remove(); return; }
  let h = `<thead><tr><th>Corpus</th>${A.columns.map((c) => `<th style="white-space:normal">${esc(c.label)}</th>`).join('')}</tr></thead><tbody>`;
  for (const r of A.rows) {
    h += `<tr><td><b>${esc(r.name)}</b><br><span class="cap">${esc(r.note || '')}</span></td>${A.columns.map((c) => `<td>${r[c.key] == null ? '–' : esc(r[c.key])}</td>`).join('')}</tr>`;
  }
  $('#ai-table').innerHTML = h + '</tbody>';
})();
