const $ = (s) => document.querySelector(s);
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const fmt = (x, d = 2) => (x == null || Number.isNaN(x)) ? '–' : Number(x).toFixed(d);
const GCOL = { mathlib: 'var(--c-mathlib)', openai: 'var(--c-openai)', 'openai-ten': 'var(--c-openai)', human: 'var(--c-human)', 'human-upstream': 'var(--c-human)', strongpnt: 'var(--c-other)' };
const GNAME = { mathlib: 'mathlib (held out)', openai: 'OpenAI math', 'openai-ten': 'OpenAI ten proofs', human: 'Human research', 'human-upstream': 'Human, upstreaming dirs', strongpnt: 'StrongPNT' };

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
$('#lede').innerHTML = DATA.text.lede;
$('#model-text').innerHTML = DATA.text.model;
$('#strip-text').innerHTML = DATA.text.strip;
$('#heat-text').innerHTML = DATA.text.heat;
$('#decomp-text').innerHTML = DATA.text.decomp;
$('#area-text').innerHTML = DATA.text.area;
$('#test-text').innerHTML = DATA.text.test;
$('#control-text').innerHTML = DATA.text.control;
$('#method').innerHTML = DATA.text.method;
$('#figs').innerHTML = DATA.figs.map((f) => `<div class="fig"><div class="v">${f.v}${f.unit ? ` <small>${f.unit}</small>` : ''}</div><div class="l">${f.l}</div></div>`).join('');

// ---------- strip ----------
const STRIP_GROUPS = ['mathlib', 'openai', 'human', 'human-upstream', 'openai-ten', 'strongpnt'];
$('#strip-legend').innerHTML = `<span><i style="background:var(--c-mathlib)"></i>mathlib</span><span><i style="background:var(--c-openai)"></i>OpenAI (hollow = certificate regime)</span><span><i style="background:var(--c-human)"></i>Human research</span><span><i style="background:var(--c-other)"></i>StrongPNT</span><span>│ median with 95% interval</span>`;
function drawStrip(metric) {
  const svg = $('#strip'); svg.innerHTML = '';
  const W = 940, H = 330, L = 190, R = 20, T = 10, B = 34;
  const vals = DATA.projects.map((p) => p[metric]).filter((v) => v != null).sort((a, b) => a - b);
  const lo = Math.floor(vals[Math.floor(vals.length * 0.002)]), hi = Math.ceil(vals[Math.floor(vals.length * 0.995)]);
  const x = (v) => L + (Math.min(Math.max(v, lo), hi) - lo) / (hi - lo) * (W - L - R);
  const rowH = (H - T - B) / STRIP_GROUPS.length;
  for (const t of ticks(lo, hi)) {
    el('line', { x1: x(t), x2: x(t), y1: T, y2: H - B, class: 'gridline' }, svg);
    el('text', { x: x(t), y: H - B + 18, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = t;
  }
  const tp = tipper($('#strip-chart'));
  let clipped = 0;
  STRIP_GROUPS.forEach((g, i) => {
    const cy = T + rowH * (i + 0.5);
    const ps = DATA.projects.filter((p) => p.group === g && p[metric] != null);
    el('text', { x: 0, y: cy - 2, 'dominant-baseline': 'middle' }, svg).textContent = GNAME[g];
    el('text', { x: 0, y: cy + 13, 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = `${ps.length} project${ps.length === 1 ? '' : 's'}`;
    for (const p of ps) {
      if (p[metric] > hi || p[metric] < lo) clipped++;
      const hollow = p.regime === 'certificate';
      const c = el('circle', { cx: x(p[metric]), cy: cy + (hash(p.project) - 0.5) * rowH * 0.62, r: ps.length > 100 ? 3 : 4.5,
        fill: hollow ? 'var(--panel)' : GCOL[g], stroke: hollow ? GCOL[g] : 'var(--panel)', 'stroke-width': hollow ? 1.5 : 0.75, 'fill-opacity': hollow ? 1 : 0.75 }, svg);
      c.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">${GNAME[g]}${hollow ? ' · certificate regime' : ''}</div><b>${p.project}</b><br>${fmt(p[metric])} bits per ${metric === 'e_tok' ? 'token' : 'reference'} · ${p.n_thm.toLocaleString()} theorems`));
      c.addEventListener('mouseleave', tp.hide);
    }
    const gm = DATA.groups.find((r) => r.group === g && r.metric === metric);
    if (gm && ps.length > 1) {
      el('line', { x1: x(gm.lo), x2: x(gm.hi), y1: cy, y2: cy, stroke: 'var(--ink)', 'stroke-width': 3, 'stroke-linecap': 'round' }, svg);
      el('line', { x1: x(gm.median), x2: x(gm.median), y1: cy - rowH * 0.38, y2: cy + rowH * 0.38, stroke: 'var(--ink)', 'stroke-width': 2 }, svg);
      el('text', { x: x(gm.median) + 6, y: cy - rowH * 0.3, style: 'fill:var(--ink);font-weight:600' }, svg).textContent = fmt(gm.median);
    }
  });
  $('#strip-cap').textContent = (metric === 'e_tok'
    ? 'Text channel: −log₂ of the token sequence under a 5-gram Kneser–Ney model of mathlib, divided by tokens. Long numerals are excluded here and counted in the literal channel.'
    : 'Premise channel: bits per resolved reference to a global constant, under mathlib’s own reference frequencies with a two-part code for bespoke constants.')
    + ` Projects with 20+ theorems.${clipped ? ` ${clipped} outlying project${clipped > 1 ? 's are' : ' is'} pinned to the axis edge.` : ''}`;
}
drawStrip('e_tok');
for (const [id, m] of [['#m-text', 'e_tok'], ['#m-prem', 'e_prem']]) {
  $(id).addEventListener('click', () => {
    $('#m-text').setAttribute('aria-pressed', m === 'e_tok'); $('#m-prem').setAttribute('aria-pressed', m === 'e_prem'); drawStrip(m);
  });
}

// ---------- heat ----------
const BINS = [2, 5, 9, 14];
const HEAT = ['var(--heat-0)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)'];
$('#heatbar').innerHTML = HEAT.map((h) => `<span style="background:${h};border:1px solid var(--rule)"></span>`).join('');
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
$('#proofs').innerHTML = DATA.heat.map((h) => {
  const body = h.spans.map(([t, b]) => {
    if (b == null) return esc(t);
    const k = BINS.findIndex((v) => b < v); const bin = k < 0 ? 4 : k;
    const ink = bin >= 3 ? 'color:var(--heat-ink-hot);' : '';
    return `<span data-b="${b}" title="${esc(t)}: ${b.toFixed(1)} bits" style="background:${HEAT[bin]};${ink}">${esc(t)}</span>`;
  }).join('');
  return `<article class="proof"><header><span><span class="who">${h.label}</span> · <span class="mono">${esc(h.project)}</span></span><span class="meta">${h.tokens} tokens · ${h.bits.toFixed(0)} bits · ${h.bits_per_tok.toFixed(2)} bits/token</span></header><pre>${esc(h.prefix)}${body}</pre></article>`;
}).join('');

// ---------- decomposition ----------
const PARTS = [['c_name', 'Name pieces', 'var(--d1)'], ['c_unk', 'Spelling coined words', 'var(--d2)'], ['c_op', 'Syntax and symbols', 'var(--d3)'], ['c_num', 'Numerals', 'var(--d4)'], ['c_end', 'End of declaration', 'var(--d5)']];
$('#decomp-legend').innerHTML = PARTS.map(([, n, c]) => `<span><i style="background:${c};border-radius:2px"></i>${n}</span>`).join('');
(function drawDecomp() {
  const svg = $('#decomp');
  const rows = DATA.decomp;
  const W = 940, L = 190, R = 60, T = 6, rowH = 34;
  const H = T + rows.length * rowH + 28;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const max = Math.ceil(Math.max(...rows.map((r) => PARTS.reduce((s, [k]) => s + r[k], 0))));
  const x = (v) => L + v / max * (W - L - R);
  for (const t of ticks(0, max)) {
    el('line', { x1: x(t), x2: x(t), y1: T, y2: H - 28, class: 'gridline' }, svg);
    el('text', { x: x(t), y: H - 10, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = t;
  }
  const tp = tipper($('#decomp-chart'));
  rows.forEach((r, i) => {
    const y = T + i * rowH + 6;
    el('text', { x: 0, y: y + 11, 'dominant-baseline': 'middle' }, svg).textContent = GNAME[r.group];
    let acc = 0;
    for (const [k, n, c] of PARTS) {
      const w = x(acc + r[k]) - x(acc);
      const rect = el('rect', { x: x(acc) + (acc ? 1 : 0), y, width: Math.max(0, w - (acc ? 1 : 0)), height: 22, fill: c, rx: 2 }, svg);
      rect.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">${GNAME[r.group]}</div><b>${n}</b>: ${fmt(r[k])} bits per token`));
      rect.addEventListener('mouseleave', tp.hide);
      acc += r[k];
    }
    el('text', { x: x(acc) + 6, y: y + 11, 'dominant-baseline': 'middle', style: 'fill:var(--ink);font-weight:600' }, svg).textContent = fmt(acc);
  });
})();

// ---------- areas ----------
(function drawAreas() {
  const svg = $('#areas');
  const rows = DATA.areas;
  const W = 940, L = 170, R = 30, T = 6, rowH = 26;
  const H = T + rows.length * rowH + 30;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const all = rows.flatMap((r) => [r.median_mathlib, r.median_openai]);
  const lo = Math.floor(Math.min(...all)) - 0.5, hi = Math.ceil(Math.max(...all)) + 0.5;
  const x = (v) => L + (v - lo) / (hi - lo) * (W - L - R);
  for (const t of ticks(lo, hi)) {
    el('line', { x1: x(t), x2: x(t), y1: T, y2: H - 30, class: 'gridline' }, svg);
    el('text', { x: x(t), y: H - 10, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = t;
  }
  const tp = tipper($('#area-chart'));
  rows.forEach((r, i) => {
    const y = T + i * rowH + rowH / 2;
    el('text', { x: 0, y, 'dominant-baseline': 'middle' }, svg).textContent = r.area.replace(/([a-z])([A-Z])/g, '$1 $2');
    el('line', { x1: x(r.median_mathlib), x2: x(r.median_openai), y1: y, y2: y, stroke: 'var(--rule)', 'stroke-width': 3 }, svg);
    for (const [k, c, n, nk] of [['median_mathlib', 'var(--c-mathlib)', 'mathlib', 'size_mathlib'], ['median_openai', 'var(--c-openai)', 'OpenAI', 'size_openai']]) {
      const d = el('circle', { cx: x(r[k]), cy: y, r: 5.5, fill: c, stroke: 'var(--panel)', 'stroke-width': 2 }, svg);
      d.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">${r.area}</div><b>${n}</b>: ${fmt(r[k])} bits/token, median of ${r[nk]} projects`));
      d.addEventListener('mouseleave', tp.hide);
    }
  });
})();

// ---------- forest ----------
function drawForest(vs) {
  const svg = $('#forest'); svg.innerHTML = '';
  const rows = DATA.tests.filter((t) => t.vs === vs);
  const W = 940, L = 230, R = 170, T = 24, rowH = 28;
  const H = T + rows.length * rowH + 8;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const cx0 = L, cw = W - L - R;
  el('text', { x: W - R + 20, y: 12, class: 'tick' }, svg).textContent = 'AUC';
  el('text', { x: W - R + 80, y: 12, class: 'tick' }, svg).textContent = 'q';
  el('line', { x1: cx0 + cw / 2, x2: cx0 + cw / 2, y1: T - 6, y2: H, class: 'axis' }, svg);
  el('text', { x: cx0 + cw / 2, y: 12, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = 'no difference';
  const tp = tipper($('#forest-chart'));
  rows.forEach((r, i) => {
    const y = T + i * rowH + rowH / 2;
    if (i % 2 === 0) el('rect', { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: 'var(--grid)', 'fill-opacity': 0.5 }, svg);
    el('text', { x: 4, y, 'dominant-baseline': 'middle' }, svg).textContent = r.label;
    const m = Math.max(Math.abs(r.lo), Math.abs(r.hi), Math.abs(r.diff)) * 1.1 || 1;
    const x = (v) => cx0 + cw / 2 + v / m * (cw / 2);
    const col = r.q < 0.05 ? 'var(--c-openai)' : 'var(--ink-3)';
    el('line', { x1: x(r.lo), x2: x(r.hi), y1: y, y2: y, stroke: col, 'stroke-width': 2.5, 'stroke-linecap': 'round' }, svg);
    const d = el('circle', { cx: x(r.diff), cy: y, r: 5, fill: col, stroke: 'var(--panel)', 'stroke-width': 1.5 }, svg);
    el('text', { x: x(r.diff), y: y - 8, 'text-anchor': 'middle', class: 'tick' }, svg).textContent = (r.diff > 0 ? '+' : '') + fmt(r.diff, Math.abs(r.diff) >= 10 ? 0 : 2);
    el('text', { x: W - R + 20, y, 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = fmt(r.auc);
    el('text', { x: W - R + 80, y, 'dominant-baseline': 'middle', class: 'tick' }, svg).textContent = r.q < 0.001 ? '<0.001' : fmt(r.q, 3);
    d.addEventListener('mousemove', (e) => tp.show(e, `<div class="t">OpenAI minus ${vs === 'human' ? 'human research' : 'held-out mathlib'}</div><b>${r.label}</b>: ${fmt(r.diff, 3)} [${fmt(r.lo, 3)}, ${fmt(r.hi, 3)}]<br>${r.n_openai} vs ${r.n_ref} projects`));
    d.addEventListener('mouseleave', tp.hide);
  });
}
drawForest('mathlib');
for (const vs of ['mathlib', 'human']) {
  $('#vs-' + vs).addEventListener('click', () => {
    $('#vs-mathlib').setAttribute('aria-pressed', vs === 'mathlib'); $('#vs-human').setAttribute('aria-pressed', vs === 'human'); drawForest(vs);
  });
}

// ---------- table ----------
(function () {
  const groups = ['mathlib', 'openai', 'openai-core', 'openai-certificate', 'human', 'human-upstream'];
  const names = { ...GNAME, 'openai-core': 'OpenAI core', 'openai-certificate': 'OpenAI certificate' };
  const metrics = [...new Set(DATA.groups.map((r) => r.metric))];
  let h = `<thead><tr><th>Median project [95% interval]</th>${groups.map((g) => `<th>${names[g]}</th>`).join('')}</tr></thead><tbody>`;
  for (const m of metrics) {
    const lab = DATA.groups.find((r) => r.metric === m);
    h += `<tr><td title="${lab.definition}">${lab.label}<br><span class="cap">${lab.definition}</span></td>`;
    for (const g of groups) {
      const r = DATA.groups.find((x) => x.metric === m && x.group === g);
      const d = Math.abs(r.median) >= 100 ? 0 : 2;
      h += `<td>${fmt(r.median, d)}<br><span class="cap">${Number.isNaN(r.lo) || r.lo == null ? '' : `${fmt(r.lo, d)}–${fmt(r.hi, d)}`}</span></td>`;
    }
    h += '</tr>';
  }
  $('#group-table').innerHTML = h + `</tbody><tfoot><tr><td class="cap">Projects</td>${groups.map((g) => `<td class="cap">${DATA.groups.find((x) => x.group === g).n}</td>`).join('')}</tr></tfoot>`;
})();
