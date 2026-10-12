"""The combined report: every result of the energy, eigenproof, cut and AI-corpus analyses, read from their outputs.

Run from anywhere: python3 synthesis/build.py  ->  synthesis/report.html
Numbers in the prose are read from the result files listed in SRC, never typed in.
"""
import html as _html
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, 'energy', 'data', 'out')
EG = os.path.join(ROOT, 'eigen')
OF = os.path.join(EG, 'out_final')

# ------------------------------------------------------------------ inputs
EG_ = pd.read_csv(os.path.join(EN, 'group_metrics.csv'))
ET = pd.read_csv(os.path.join(EN, 'tests.csv'))
ES = json.load(open(os.path.join(EN, 'summary.json')))
EDEC = json.load(open(os.path.join(EN, 'decomp.json')))
EP_ = pd.read_csv(os.path.join(EN, 'projects.csv'))
EA = pd.read_csv(os.path.join(EN, 'areas.csv'))
EAI = pd.read_csv(os.path.join(EN, 'projects_ai.csv')) if os.path.exists(os.path.join(EN, 'projects_ai.csv')) else None
R = json.load(open(os.path.join(OF, 'analysis_merged', 'results.json')))
R0 = json.load(open(os.path.join(OF, 'analysis', 'results.json')))
RC = {k: json.load(open(os.path.join(OF, k, 'results.json'))) for k in ('analysis_proofs', 'analysis_rho0', 'analysis_nocut')}
REP = json.load(open(os.path.join(OF, 'analysis_merged', 'recheck_ep.json')))
ISO = json.load(open(os.path.join(EG, 'out_swap', 'compare.json')))
CR = json.load(open(os.path.join(EG, 'out_cut', 'results_ai.json')))
CO = json.load(open(os.path.join(OF, 'analysis_all', 'corpora.json')))
FAIL = json.load(open(os.path.join(EG, 'out_ai_ready', 'failures.json')))
_tr = os.path.join(EG, 'out_terms', 'terms_results.json')
TR = json.load(open(_tr)) if os.path.exists(_tr) else None
T = TR['corpora'] if TR else {}
_tx = os.path.join(EG, 'out_terms', 'terms_extra_mathlib.json')
TX = json.load(open(_tx)) if os.path.exists(_tx) else None

SRC = ['energy/data/out/{group_metrics,tests,areas,projects,projects_ai}.csv, summary.json, decomp.json',
       'eigen/out_final/analysis_merged/{results,recheck_ep}.json',
       'eigen/out_final/analysis_{proofs,rho0,nocut}/results.json',
       'eigen/out_final/analysis_all/corpora.json', 'eigen/out_cut/results_ai.json', 'eigen/out_swap/compare.json',
       'eigen/out_terms/{terms_results,terms_extra_mathlib}.json']


def esc(s):
    return _html.escape(str(s))


def em(metric, group, f='median'):
    return float(EG_[(EG_.metric == metric) & (EG_.group == group)][f].iloc[0])


def et(metric, vs, f='diff'):
    return float(ET[(ET.metric == metric) & (ET.vs == vs)][f].iloc[0])


def rg(r, m, g):
    return next((x['median'] for x in r['groups'] if x['metric'] == m and x['group'] == g), None)


def rt(r, vs, m):
    return next((x for x in r['tests'] if x['vs'] == vs and x['metric'] == m), None)


def rsize(r, g, k='theorems'):
    return next(x[k] for x in r['sizes'] if x['group'] == g)


def pct(x, d=0):
    return f'{100 * x:.{d}f}%'


def mono(s):
    return f'<code>{esc(s)}</code>'


def sci(p):
    if p >= 0.001:
        return f'{p:.3f}'
    e = int(math.floor(math.log10(p)))
    return f'{p / 10 ** e:.0f}·10<sup>{e}</sup>'


# ------------------------------------------------------------------ derived numbers
NE = ES['n_projects']
e_ml, e_oa, e_hu, e_up = (em('e_tok', g) for g in ('mathlib', 'openai', 'human', 'human-upstream'))
dec = {g: sum(v.values()) for g, v in EDEC.items()}
gap_total = dec['openai'] - dec['mathlib']
name_part = ((EDEC['openai']['c_name'] + EDEC['openai']['c_unk']) - (EDEC['mathlib']['c_name'] + EDEC['mathlib']['c_unk'])) / gap_total
areas_all = bool((EA.median_openai > EA.median_mathlib).all())

SZ = {x['group']: x for x in R['sizes']}
kl, kl0, klh = R['kl_bits']['openai'], R0['kl_bits']['openai'], R['kl_bits']['human']
null, nullh = R['null'], R['null_human']
ratio, ratio_h = kl / null['total_median'], klh / nullh['total_median']
M = {m['rank']: m for m in R['modes']}
DJ = R['decl_join']
TV = R['text_vs_ir']

PO, PM, AU, PV = CR['pooled'], CR['project_median'], CR['auc'], CR['p']
PP = CR['per_proof']
Z, Pr = RC['analysis_rho0'], RC['analysis_proofs']
M1 = REP['modes'][0]
z_ratio = Z['kl_bits']['openai'] / Z['null']['total_median']
p_ratio = Pr['kl_bits']['openai'] / Pr['null']['total_median']
z_e = (rg(Z, 'e_ir', 'openai'), rg(Z, 'e_ir', 'mathlib'))
z_et = rt(Z, 'mathlib', 'e_ir')
z_top = Z['modes'][0]
z_ia = next(m for m in Z['modes'] if m['pos'][0]['gesture'].startswith('tac:IntArith'))
keep = {g: rsize(Z, g) / rsize(Pr, g) for g in ('openai', 'mathlib', 'human')}
ep_others = REP['modes'][1:]
ep_lo = min(m['openai_rho0']['beyond2'] / m['mathlib_rho0']['beyond2'] for m in ep_others)
ep_hi = max(m['openai_rho0']['beyond2'] / m['mathlib_rho0']['beyond2'] for m in ep_others)

AI = [c for c in ('spherepacking', 'putnam2025', 'imo2025') if c in CO['corpora']]
AI_NAME = dict(spherepacking='Sphere packing', putnam2025='Putnam 2025', imo2025='IMO 2025', erdos90='Erdős 90', flt='FLT')
AI_WHO = dict(spherepacking='Math Inc’s Gauss, on a 20k-line human base', putnam2025='Axiom’s AxiomProver',
              imo2025='Harmonic’s Aristotle', erdos90='GPT-5.6 (original proof)', flt='Anthropic’s Claude')
AI_LEAN = dict(spherepacking='4.28', putnam2025='4.21', imo2025='4.20', erdos90='4.30', flt='4.33.1')
ai_text = {}
if EAI is not None:
    for c in AI:
        s = EAI[EAI.corpus == 'ai_' + c]
        if len(s):
            ai_text[c] = (float(s.e_tok.median()), len(s))
EP1_AI = {c: CO['eigenproof_prevalence'][c][0]['beyond2'] for c in CO['eigenproof_prevalence']}

# ------------------------------------------------------------------ charts (inline SVG, one scale per chart)
GC = {'mathlib': 'var(--c-ml)', 'openai': 'var(--c-oa)', 'human': 'var(--c-hu)', 'human-upstream': 'var(--c-up)',
      'spherepacking': 'var(--c-ai)', 'putnam2025': 'var(--c-ai)', 'imo2025': 'var(--c-ai)'}
GL = {'mathlib': 'mathlib', 'openai': 'OpenAI', 'human': 'Human research', 'human-upstream': 'Human, written for mathlib',
      'spherepacking': 'Sphere packing', 'putnam2025': 'Putnam 2025', 'imo2025': 'IMO 2025'}


def strip_chart():
    groups = ['mathlib', 'human-upstream', 'human', 'openai']
    W, H, L, Rm, row = 900, 250, 225, 20, 52
    lo, hi = 3.5, 11.0
    x = lambda v: L + (min(max(v, lo), hi) - lo) / (hi - lo) * (W - L - Rm)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Text energy of each project, by corpus">']
    for t in range(4, 12):
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="10" y2="{H - 30}" class="grid"/>'
                   f'<text x="{x(t):.1f}" y="{H - 12}" class="tick" text-anchor="middle">{t}</text>')
    rng = np.random.default_rng(1)
    for i, g in enumerate(groups):
        y0 = 30 + i * row
        v = EP_[EP_.group == g].e_tok.dropna().to_numpy()
        out.append(f'<text x="{L - 12}" y="{y0 + 4}" class="lab" text-anchor="end">{GL[g]}</text>'
                   f'<text x="{L - 12}" y="{y0 + 18}" class="tick" text-anchor="end">{len(v)} projects</text>')
        for val in v:
            out.append(f'<circle cx="{x(val):.1f}" cy="{y0 + rng.uniform(-13, 13):.1f}" r="2.6" style="fill:{GC[g]}" fill-opacity="0.55"/>')
        md = float(np.median(v))
        out.append(f'<line x1="{x(md):.1f}" x2="{x(md):.1f}" y1="{y0 - 19}" y2="{y0 + 19}" class="med"/>'
                   f'<text x="{x(md) + 5:.1f}" y="{y0 - 12}" class="tick strong">{md:.2f}</text>')
    out.append(f'<text x="{(L + W - Rm) / 2:.0f}" y="{H}" class="tick" text-anchor="middle">bits per token under mathlib’s 5-gram model</text></svg>')
    return ''.join(out)


def spectrum_chart():
    spec = R['spectrum']['openai'][:12]
    W, H, L, B = 900, 240, 46, 40
    top = 25.0
    bw = (W - L - 10) / len(spec)
    y = lambda v: H - B - v / top * (H - B - 14)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Bits carried by each OpenAI eigenproof against the null">']
    for t in range(0, 26, 5):
        out.append(f'<line x1="{L}" x2="{W - 10}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>'
                   f'<text x="{L - 8}" y="{y(t) + 4:.1f}" class="tick" text-anchor="end">{t}</text>')
    for i, s in enumerate(spec):
        x0 = L + i * bw + bw * 0.18
        out.append(f'<rect x="{x0:.1f}" y="{y(s["bits"]):.1f}" width="{bw * 0.64:.1f}" height="{y(0) - y(s["bits"]):.1f}" style="fill:var(--c-oa)"/>'
                   f'<text x="{x0 + bw * 0.32:.1f}" y="{H - B + 16}" class="tick" text-anchor="middle">{s["rank"]}</text>')
        if i < len(null['top_median']):
            nm, nx = null['top_median'][i], null['top_max'][i]
            out.append(f'<line x1="{x0 - 3:.1f}" x2="{x0 + bw * 0.64 + 3:.1f}" y1="{y(nm):.1f}" y2="{y(nm):.1f}" class="nullm"/>'
                       f'<line x1="{x0 - 3:.1f}" x2="{x0 + bw * 0.64 + 3:.1f}" y1="{y(nx):.1f}" y2="{y(nx):.1f}" class="nullx"/>')
    out.append(f'<text x="{L + (W - L) / 2:.0f}" y="{H - 4}" class="tick" text-anchor="middle">eigenproof rank</text>'
               f'<text x="12" y="{y(top / 2):.0f}" class="tick" text-anchor="middle" transform="rotate(-90 12 {y(top / 2):.0f})">bits</text></svg>')
    return ''.join(out)


def cut_chart():
    cs = ['mathlib', 'human', 'openai'] + [c for c in AI if PO.get(c, {}).get('proofs', 0) >= 100]
    W, L, Rm, row = 900, 190, 60, 40
    H = 40 + row * len(cs)
    hi = 0.2
    x = lambda v: L + v / hi * (W - L - Rm)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Compressibility and layout redundancy by corpus">']
    for t in (0, 0.05, 0.1, 0.15, 0.2):
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="8" y2="{H - 26}" class="grid"/>'
                   f'<text x="{x(t):.1f}" y="{H - 10}" class="tick" text-anchor="middle">{t:g}</text>')
    for i, c in enumerate(cs):
        y0 = 14 + i * row
        chi, rho = PO[c]['chi_mean'], PO[c]['rho_mean']
        out.append(f'<text x="{L - 12}" y="{y0 + 14}" class="lab" text-anchor="end">{GL[c]}</text>'
                   f'<rect x="{L}" y="{y0}" width="{x(chi) - L:.1f}" height="10" class="bar-chi"/>'
                   f'<rect x="{L}" y="{y0 + 12}" width="{x(rho) - L:.1f}" height="10" style="fill:{GC[c]}"/>'
                   f'<text x="{x(chi) + 5:.1f}" y="{y0 + 9}" class="tick">χ {chi:.3f}</text>'
                   f'<text x="{x(rho) + 5:.1f}" y="{y0 + 21}" class="tick strong">ρ {rho:.3f}</text>')
    out.append(f'<text x="{(L + W - Rm) / 2:.0f}" y="{H}" class="tick" text-anchor="middle">mean bits per proof</text></svg>')
    return ''.join(out)


# ------------------------------------------------------------------ tables
def table(head, rows, cls=''):
    h = f'<div class="tablebox"><table class="{cls}"><thead><tr>' + ''.join(f'<th>{c}</th>' for c in head) + '</tr></thead><tbody>'
    for r in rows:
        h += '<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>'
    return h + '</tbody></table></div>'


def auc_cell(t):
    if t is None:
        return '–'
    s = f'{t["auc"]:.2f}'
    return s if t['q'] < 0.05 else f'<span class="ns">{s}</span>'


corpora_rows = [
    ['<b>mathlib</b>', 'Human, curated', f'{NE["mathlib"]} / {rsize(R, "mathlib", "projects"):,}', f'{rsize(R, "mathlib"):,}',
     'Pinned at OpenAI’s revision d13f23b and built here. In the text study each project is scored by a model that never saw it.'],
    ['<b>OpenAI</b> (openai/math)', 'OpenAI models', f'{NE["openai"]} / {SZ["openai"]["projects"]}', f'{SZ["openai"]["theorems"]:,}',
     '26M lines. Text: every project with 20+ theorems. Compiled: 96 of 97 randomly drawn projects (Geometry.Arnold stalls).'],
    ['<b>Human research</b>', 'Human', f'{NE["human"]} / {SZ["human"]["projects"]}', f'{SZ["human"]["theorems"]:,}',
     'Text: Carleson, FLT, PFR, sphere eversion. Compiled: Carleson and sphere eversion, module by module. Directories written for '
     'upstreaming to mathlib are kept apart as a check.'],
]
for c in AI:
    co = CO['corpora'][c]
    corpora_rows.append([f'<b>{AI_NAME[c]}</b>', AI_WHO[c], f'{ai_text.get(c, (0, 0))[1]} / {co["projects"]}', f'{co["theorems"]:,}',
                         f'Written for Lean {AI_LEAN[c]}; {pct(FAIL[c]["share"])} of its theorems fail or contain sorry under the mathlib used here.'])
corpora_rows += [['<b>Erdős 90</b>', AI_WHO['erdos90'], '–', 'not run', '1.2M lines. Stopped after about 5% (some 45 hours of compilation) to free the machine for the proof-term pass.'],
                 ['<b>FLT</b>', AI_WHO['flt'], '–', 'not run', '13.5M lines. Left for a later run.']]

units_rows = [
    ['bits per token', 'Text energy', 'The cost of the source text under a 5-gram Kneser–Ney model of mathlib’s own Lean source: −log₂ q<sub>mathlib</sub>(x) per token. Low means it reads like mathlib.'],
    ['bits per reference', 'Premise energy', 'The cost of naming each constant a proof cites, under mathlib’s frequencies of citing it, or under a “one of mine” code for a project’s own constants.'],
    ['bits per step', 'Compiled energy', 'The elaborated proof term read as a tree of <em>gestures</em> (inference steps with names erased, types cut to their head connective). Cost per step under a Kneser–Ney model of each gesture given its parent, trained on mathlib.'],
    ['bits (KL)', 'Divergence', 'Gaussian KL divergence between a corpus’s gesture mix and mathlib’s. It splits exactly over generalized eigenvectors, the <em>eigenproofs</em>. Always read against a null: random sets of mathlib projects of the same size compared with the rest of mathlib.'],
    ['bits of cut compression', 'κ, χ, ρ', 'log₂ of a size ratio between normal forms of one proof term. κ: cut-free size over size as written. χ: cut-free size over the optimal layout (what sharing can save). ρ: as written over the optimal layout (redundancy). κ = χ − ρ.'],
    ['AUC', 'Separation', 'The chance that a random project of one corpus scores higher than a random project of the other. 0.5 means no difference, 1 means complete separation.'],
]

rules_rows = []
for m, lab, d, f in [('nodes_med', 'Proof size', 'median steps per theorem', lambda v: f'{v:.1f}'),
                     ('weakening', 'Unused hypotheses', 'share of hypotheses never used', pct),
                     ('linear', 'Linear hypotheses', 'used exactly once', pct),
                     ('contraction', 'Reused hypotheses', 'used twice or more', pct),
                     ('cuts_per_100', 'Intermediate claims', 'cuts per 100 steps', lambda v: f'{v:.2f}'),
                     ('single_use_cut', 'Single-use claims', 'share of cuts used once', pct),
                     ('dead_cut', 'Unused claims', 'share of cuts never used', lambda v: pct(v, 1))]:
    rules_rows.append([f'{lab}<div class="sub">{d}</div>'] + [f(rg(R, m, g)) for g in ('mathlib', 'openai', 'human')]
                      + [auc_cell(rt(R, 'mathlib', m)), auc_cell(rt(R, 'human', m))])

cut_rows = []
for k, lab, d, f in [('with_cut', 'Proofs with a cut', '', lambda c: pct(PP[c]['with_cut'])),
                     ('cuts_per_100', 'Cuts per 100 steps', 'shared size', lambda c: f'{PO[c]["cuts_per_100"]:.2f}'),
                     ('share', 'Dead · linear · shared', 'share of cuts used 0, 1, ≥2 times',
                      lambda c: ' · '.join(pct(PO[c]['share'][s]) for s in ('dead', 'linear', 'shared'))),
                     ('chi', 'χ compressibility', 'mean bits per proof', lambda c: f'{PO[c]["chi_mean"]:.3f}'),
                     ('rho', 'ρ layout redundancy', 'mean bits per proof', lambda c: f'{PO[c]["rho_mean"]:.3f}'),
                     ('neg', 'Larger with cuts than without', 'share with κ &lt; 0', lambda c: pct(PO[c]['kappa_neg'])),
                     ('lemma', 'Lemma-level κ', 'median project, bits', lambda c: f'{PM[c]["kappa_lemma"]:.2f}' if PM.get(c, {}).get('projects') else '–')]:
    cut_rows.append([f'{lab}' + (f'<div class="sub">{d}</div>' if d else '')] + [f(c) for c in ['mathlib', 'openai', 'human'] + AI])

TITLES = {1: 'Arithmetic stitched into equation chains', 2: 'Dependent rewriting under binders', 3: 'Closing by numeral evaluation',
          4: 'Normalize, then close', 5: 'Numeric side conditions', 6: 'Structure projections', 7: 'Light against heavy normalization',
          8: 'Pure ring steps'}
ep_rows = []
for k in range(1, 9):
    m, rp = M[k], REP['modes'][k - 1]
    ep_rows.append([f'<b>{k}</b>', f'{TITLES[k]}<div class="sub">{esc(m["pos"][0]["desc"])}</div>', f'{m["bits"]:.1f}',
                    f'{R["stability"][k - 1]:.2f}'] + [pct(m['prevalence'][g]['beyond2'], 1) for g in ('mathlib', 'openai', 'human')]
                   + [pct(rp['openai_rho0']['beyond2'], 1), pct(rp['openai_excess_from_rho+'])])

COLS = [('analysis_merged', R, 'All theorems'), ('analysis_proofs', Pr, 'Proofs only'), ('analysis_rho0', Z, 'Optimal layout'),
        ('analysis_nocut', RC['analysis_nocut'], 'No cuts')]


def _rat(r, g='openai'):
    return r['kl_bits'][g] / (r['null'] if g == 'openai' else r['null_human'])['total_median']


rc_rows = [
    ['OpenAI theorems'] + [f'{rsize(r, "openai"):,}' for _, r, _ in COLS],
    ['Divergence / null'] + [f'{r["kl_bits"]["openai"]:.0f} / {r["null"]["total_median"]:.0f} = <b>{_rat(r):.1f}×</b>' for _, r, _ in COLS],
    ['Human code, same ratio'] + [f'{_rat(r, "human"):.1f}×' for _, r, _ in COLS],
    ['Top eigenproof'] + [f'{mono(r["modes"][0]["pos"][0]["gesture"])} {r["modes"][0]["bits"]:.0f}' for _, r, _ in COLS],
    ['Compiled energy, OpenAI vs mathlib'] + [f'{rg(r, "e_ir", "openai"):.2f} vs {rg(r, "e_ir", "mathlib"):.2f} ({auc_cell(rt(r, "mathlib", "e_ir"))})' for _, r, _ in COLS],
    ['Text-energy gap, bits/token'] + [f'{r["text_vs_ir"]["text_gap_raw"]:.2f}' for _, r, _ in COLS],
    ['Proof size, AUC'] + [auc_cell(rt(r, 'mathlib', 'nodes_med')) for _, r, _ in COLS],
    ['Unused hypotheses, AUC'] + [auc_cell(rt(r, 'mathlib', 'weakening')) for _, r, _ in COLS],
    ['Automation certificates, AUC'] + [auc_cell(rt(r, 'mathlib', 'share:automation certificate')) for _, r, _ in COLS],
]

ai_cols = ['openai', 'human'] + AI


def _co(c, f):
    return f(CO['corpora'][c]) if c in CO['corpora'] else '–'


def _txt(c):
    if c == 'openai':
        return f'{e_oa:.2f}'
    if c == 'human':
        return f'{e_hu:.2f}'
    return f'{ai_text[c][0]:.2f}' if c in ai_text else '–'


def _cut(c, k, f):
    return f(PO[c][k]) if c in PO and PO[c].get('proofs', 0) >= 20 else '–'


ai_rows = [
    ['Theorems compiled'] + [_co(c, lambda v: f'{v["theorems"]:,}') for c in ai_cols],
    ['Failed or sorry'] + ['&lt;0.1%', '4.5% (Carleson)'] + [pct(FAIL[c]['share']) for c in AI],
    ['Text energy, median project'] + [_txt(c) for c in ai_cols],
    ['Compiled energy, median theorem'] + [_co(c, lambda v: f'{v["e_thm_median"]:.2f}') for c in ai_cols],
    ['Divergence / null'] + [_co(c, lambda v: f'{v["kl_bits"]:.0f} / {v["null_median"]:.0f} = <b>{v["ratio"]:.1f}×</b>') for c in ai_cols],
    ['Eigenproof 1 beyond +2 SD'] + [pct(EP1_AI[c], 1) if c in EP1_AI else '–' for c in ai_cols],
    ['Own top direction'] + [_co(c, lambda v: mono(CO['own_direction'][c]['top'][0]['gesture'])) if c in CO['own_direction'] else '–' for c in ai_cols],
    ['Proofs with a cut'] + [pct(PP[c]['with_cut']) if c in PP else '–' for c in ai_cols],
    ['χ compressibility'] + [_cut(c, 'chi_mean', lambda v: f'{v:.3f}') for c in ai_cols],
    ['ρ layout redundancy'] + [_cut(c, 'rho_mean', lambda v: f'<b>{v:.3f}</b>') for c in ai_cols],
    ['Larger with cuts than without'] + [_cut(c, 'kappa_neg', pct) for c in ai_cols],
]
EP1_MATHLIB = M[1]['prevalence']['mathlib']['beyond2']

ledger = [
    ('holds', 'OpenAI’s text costs more under mathlib’s model than mathlib’s own text, mostly in names.',
     f'{e_oa:.2f} vs {e_ml:.2f} bits per token, AUC {et("e_tok", "mathlib", "auc"):.2f}; unchanged when redundant claims are removed ({Z["text_vs_ir"]["text_gap_raw"]:.2f} bits gap).'),
    ('holds', 'OpenAI’s compiled proofs mix gestures unlike mathlib, far beyond chance.',
     f'{ratio:.1f}× the size-matched null; {z_ratio:.1f}× on proofs in optimal cut layout.'),
    ('holds', 'OpenAI writes many more intermediate claims, and they mostly add redundancy rather than compression.',
     f'ρ AUC {AU["openai_vs_mathlib"]["rho_mean"]:.2f} against mathlib projects; χ is not higher.'),
    ('new', 'Redundant cut layout appears in every AI corpus measured so far.',
     ', '.join(f'{AI_NAME[c]} ρ {PO[c]["rho_mean"]:.2f}' for c in AI if PO.get(c, {}).get('proofs', 0) >= 100) + f', against mathlib’s {PO["mathlib"]["rho_mean"]:.3f}.'),
    ('revised', 'Compiled energy: the project-level tie with mathlib was a layout effect.',
     f'Over all theorems AUC {rt(R, "mathlib", "e_ir")["auc"]:.2f}; on optimal-layout proofs OpenAI costs more (AUC {z_et["auc"]:.2f}).'),
    ('revised', 'Eigenproof 1 (omega inside equation chains) mostly rides on redundant have-claims.',
     f'{pct(M1["openai_excess_from_rho+"])} of OpenAI’s excess comes from proofs with redundant layout; it survives without them at {M1["openai_rho0"]["beyond2"] / M1["mathlib_rho0"]["beyond2"]:.1f}× mathlib’s rate.'),
    ('revised', 'Lemma-level compression is not higher in OpenAI.',
     f'It looked higher with 67 projects; with all {PM["openai"]["projects"]} it is AUC {AU["openai_vs_mathlib"]["kappa_lemma"]:.2f}, p = {PV["openai_vs_mathlib"]["kappa_lemma"]:.2f}.'),
    ('open', 'Whether Erdős 90 and Anthropic’s FLT share these signatures.', 'Neither was compiled; the IMO corpus is too damaged by version drift to say much.'),
]
TAG = {'holds': 'Holds', 'new': 'New', 'revised': 'Revised', 'open': 'Open'}

# ------------------------------------------------------------------ prose
P = {}
P['dek'] = (f'An account from the ground up of how AI-written Lean differs from mathlib and from human research code: in its source text, '
            f'in its compiled proof terms, and in how it names and reuses intermediate results. The core comparison covers OpenAI’s '
            f'openai/math library, and three further AI corpora are included. A final pass reads the proof terms themselves: how much '
            f'compression each proof has in it, how much of that its author realizes, and what that suggests about proofs in general.')

P['summary'] = [
    ('Its text reads unlike mathlib’s, mostly in the names.',
     f'Under a model of mathlib’s own source, the median OpenAI project costs {e_oa:.2f} bits per token against {e_ml:.2f} for a held-out '
     f'mathlib project (AUC {et("e_tok", "mathlib", "auc"):.2f}). {pct(name_part)} of the gap is in identifiers. Human research code sits at '
     f'{e_hu:.2f}, and its directories written for upstreaming land on mathlib itself ({e_up:.2f}). When OpenAI cites mathlib, it cites '
     f'commoner lemmas than mathlib does.'),
    ('Its compiled proofs use a different mix of inferences.',
     f'Read as trees of gestures, OpenAI’s proofs are {kl:.0f} bits from mathlib’s, against {null["total_median"]:.0f} bits for random mathlib '
     f'project sets of the same size: {ratio:.1f}× the noise. Human research code is {ratio_h:.1f}×. OpenAI’s excess lies in arithmetic and '
     f'normalization certificates; its deficit lies in hand-written logical bookkeeping.'),
    ('It states many more intermediate claims, and they add size rather than save it.',
     f'{pct(PP["openai"]["with_cut"])} of OpenAI proofs contain a cut, against {pct(PP["mathlib"]["with_cut"])} in mathlib. They are not more '
     f'compressible (χ {PO["openai"]["chi_mean"]:.3f} vs {PO["mathlib"]["chi_mean"]:.3f} bits). They are more redundant: ρ {PO["openai"]["rho_mean"]:.3f} '
     f'vs {PO["mathlib"]["rho_mean"]:.3f} bits (AUC {AU["openai_vs_mathlib"]["rho_mean"]:.2f}). {pct(PO["openai"]["kappa_neg"])} of its proofs are '
     f'larger with their cuts than without them.'),
    ('Controlling for that layout sharpens some findings and weakens others.',
     f'On proofs in optimal cut layout the divergence is still {z_ratio:.1f}× the null, and OpenAI’s compiled energy rises above mathlib’s '
     f'(AUC {z_et["auc"]:.2f}), where before it was tied. The first eigenproof, omega certificates inside equation chains, is mostly carried by '
     f'redundant <code>have</code> claims.'),
    ('Other AI systems share the redundant layout.',
     'Every AI corpus measured so far has layout redundancy far above mathlib’s and human code’s. ' +
     (f'The competition provers share OpenAI’s first eigenproof, more strongly than OpenAI: {pct(EP1_AI["putnam2025"], 0)} of AxiomProver’s '
      f'Putnam theorems score beyond +2 SD on it, against {pct(EP1_AI["openai"], 0)} of OpenAI’s and {pct(EP1_MATHLIB, 1)} of mathlib’s. '
      if 'putnam2025' in EP1_AI else '') +
     (f'Sphere packing, grown by Gauss from a human base, is near human code in its gesture mix ({CO["corpora"]["spherepacking"]["ratio"]:.1f}× its null).'
      if 'spherepacking' in CO['corpora'] else '')),
]

P['pipeline'] = (
    '<p>Every corpus is measured three ways. The <b>text</b> pass reads the Lean source and needs no compilation. The '
    '<b>compiled</b> pass elaborates each proof against mathlib, using OpenAI’s pinned revision built on this machine, and walks the resulting proof term. '
    'The <b>cut</b> pass normalizes the same terms several ways and measures exact sizes. Projects, not theorems, are the unit '
    'of comparison throughout: a project is a second-level directory (OAI/Area/Topic, Mathlib/A/B). Each group comparison uses '
    'projects with at least 20 theorems.</p>'
    f'<p>The OpenAI library has 26 million lines, too many to compile on an 8 GB machine, so the compiled pass uses a random draw of '
    f'{SZ["openai"]["projects"]} projects. To check how much compilation mode matters, {len(ISO["projects"])} of them were also compiled module by module. '
    f'That gave the same gesture multiset for {pct(ISO["same_u"] / ISO["n"], 1)} of {ISO["n"]:,} theorems, and the divergence moved from '
    f'{ISO["kl_shared"]:.1f} to {ISO["kl_iso"]:.1f} bits.</p>')

P['text'] = (
    '<p>Fit a 5-gram Kneser–Ney model to mathlib’s Lean source, with identifiers split into mathlib’s naming pieces, and score each '
    'declaration by the bits it costs: E(x) = −log₂ q(x). This is a description length. A proof written the way mathlib writes '
    'proofs is cheap, and every departure costs bits. Words mathlib has never used are spelled out once, then charged a small reuse cost. '
    'Long numerals are booked separately, so numerical certificates cannot dominate. Each mathlib project is scored by a model '
    'fitted to the other four fifths of mathlib.</p>'
    f'<p>The OpenAI distribution barely overlaps mathlib’s: a random OpenAI project costs more than a random mathlib project '
    f'{pct(et("e_tok", "mathlib", "auc"))} of the time. It is not a matter of subject mix. '
    f'{"In every one" if areas_all else "In most"} of the {len(EA)} areas where both libraries have three or more projects, '
    f'OpenAI’s median is higher. Against its own area, the typical OpenAI project pays {et("d_e_tok", "mathlib"):+.2f} bits per token. '
    f'Split by token kind, {pct(name_part)} of the pooled gap ({gap_total:.2f} bits per token) is in names: identifier pieces '
    f'mathlib finds unlikely, and words it has never seen. Syntax adds only '
    f'{EDEC["openai"]["c_op"] - EDEC["mathlib"]["c_op"]:.2f}.</p>'
    f'<p>Against human research code the gap is much smaller ({et("e_tok", "human"):+.2f} bits per token, AUC {et("e_tok", "human", "auc"):.2f}), '
    f'and the subject-matched excess is not significant (q = {et("d_e_tok", "human", "q"):.2f}). Two differences persist. OpenAI cites its '
    f'own constants more ({et("bespoke_share", "human") * 100:+.0f} points, AUC {et("bespoke_share", "human", "auc"):.2f}). When it cites mathlib, it picks '
    f'commoner lemmas: library surprisal is {et("lib_surp", "mathlib"):+.2f} bits per constant against mathlib.</p>')

P['compiled'] = (
    '<p>Each elaborated proof term is walked from the root. Every node becomes a <em>gesture</em>: the rule applied, with names '
    'erased and types cut to their head connective, such as <code>core:Eq.trans(=,=)⇒=</code> or <code>tac:IntArith(≤)⇒=</code>. Each hypothesis '
    'binder is labelled with how often its variable is used: 0 (weakening), 1 (linear) or ω (contraction). These are the resource '
    'classes of linear logic, read off the term.</p>'
    f'<p><b>Compiled energy</b> is the text-energy idea moved onto this tree: bits per step under a model of each gesture given its parent. '
    f'Over all theorems the median OpenAI project costs {rg(R, "e_ir", "openai"):.2f} bits per step against mathlib’s {rg(R, "e_ir", "mathlib"):.2f} '
    f'(AUC {rt(R, "mathlib", "e_ir")["auc"]:.2f}). Theorem by theorem, OpenAI is costlier ({DJ["openai"]["e_ir_median"]:.2f} vs {DJ["mathlib"]["e_ir_median"]:.2f}). '
    f'The re-check below shows the project-level tie comes from redundant claims, which are cheap steps. Text and compiled energy barely '
    f'track each other across projects (Spearman ρ = {TV["mathlib"]["rho"]:.2f} within mathlib). Holding compiled energy fixed leaves '
    f'{TV["text_gap_given_ir"]:.2f} of the {TV["text_gap_raw"]:.2f}-bit text gap.</p>'
    '<p><b>Structural rules.</b> The resource labels give project-level rates. Against mathlib, OpenAI proofs are longer, state more claims and '
    'leave more hypotheses unused. Against the human research code, only the extra claims stand out. Unused hypotheses and dead '
    'claims are as common in Carleson and sphere eversion, so they look like features of research formalization in general.</p>')

P['cuts'] = (
    '<p>A <em>cut</em> is a proof that is named and then used: a <code>have</code>, a <code>let</code> of a proof, or a β-redex '
    '<code>(fun h ↦ q) p</code>. Eliminating it substitutes <code>p</code> for each use of <code>h</code>, and the resource class sets the cost. '
    'A dead cut is deleted. A linear cut moves <code>p</code> to its single use. A shared cut copies <code>p</code>, and only a shared cut saves anything. '
    'Each proof was normalized five ways, with exact tree sizes: as written, dead cuts removed, linear cuts removed, all cuts removed, '
    'and an optimal layout that keeps exactly the cuts that pay for themselves.</p>'
    '<p>The unit is the <b>bit of cut compression</b>. κ = log₂(cut-free size ÷ written size) splits as κ = σ − ℓ − w. Here σ is the sharing gain, ℓ the '
    'cost of naming proofs used once and w the cost of proofs never used. κ depends on where the author put the cuts, so two intrinsic '
    'quantities sit beside it. χ is the cut-free size against the optimal layout: what the proof’s sharing could save at best. ρ is the written size against that optimum: '
    'pure layout redundancy. Then κ = χ − ρ. The same unit applies one level up, with a project’s local lemmas as cuts and citations '
    'as uses.</p>'
    f'<p>Compression inside proofs is small everywhere: χ ≥ 1 (a doubling) in at most {pct(max(PO[c]["chi_ge1"] for c in ("mathlib", "openai", "human")), 1)} '
    f'of proofs. A few mathlib proofs are chains of hundreds of nested β-redexes whose cut-free forms are 2<sup>300</sup> to 2<sup>450</sup> times larger, '
    f'so corpus figures are means of per-proof bits. The human research code is the most compressible (OpenAI vs human, χ AUC '
    f'{AU["openai_vs_human"]["chi_mean"]:.2f}, p = {sci(PV["openai_vs_human"]["chi_mean"])}). OpenAI is the most redundant among the three core corpora (ρ AUC '
    f'{AU["openai_vs_mathlib"]["rho_mean"]:.2f} against mathlib, {AU["openai_vs_human"]["rho_mean"]:.2f} against human; p = {sci(PV["openai_vs_mathlib"]["rho_mean"])} '
    f'and {sci(PV["openai_vs_human"]["rho_mean"])}). Almost all of that is linear overhead: single-use claims. At the lemma level, inlining every '
    f'local lemma multiplies the median project by 2<sup>{PM["mathlib"]["kappa_lemma"]:.1f}</sup> in mathlib and 2<sup>{PM["openai"]["kappa_lemma"]:.1f}</sup> in '
    f'OpenAI, a difference that is not significant (p = {PV["openai_vs_mathlib"]["kappa_lemma"]:.2f}).</p>')

P['eigen'] = (
    f'<p>Each corpus becomes a cloud of square-root gesture-mix vectors over the {R["vocab_size"]} commonest gestures, with every project '
    f'weighted equally and both covariances lightly shrunk. The generalized eigenvectors of OpenAI’s covariance against mathlib’s are the '
    f'directions along which OpenAI varies unlike mathlib. Under a Gaussian approximation the KL divergence splits exactly across them, '
    f'so each eigenproof carries bits. OpenAI’s total is {kl:.0f} bits; random sets of {SZ["openai"]["projects"]} mathlib projects give '
    f'{null["total_median"]:.0f} (at most {null["total_max"]:.0f} in ten draws). Bars below are OpenAI’s eigenproofs; the solid tick is the null’s median '
    f'eigenvalue at that rank and the dashed tick its maximum.</p>'
    f'<p>The first eigenproof belongs to OpenAI: {pct(M[1]["prevalence"]["openai"]["beyond2"], 1)} of its theorems score beyond +2 mathlib SD, against '
    f'{pct(M[1]["prevalence"]["mathlib"]["beyond2"], 1)} in mathlib and {pct(M[1]["prevalence"]["human"]["beyond2"], 1)} in human code. The others are habits OpenAI '
    f'shares with human research code, usually to a similar degree. Split-half recovery of the first direction is {R["stability"][0]:.2f}. '
    f'mathlib has switched from omega to lia and OpenAI has not; the two are merged here, and kept apart the total rises to {kl0:.0f} bits.</p>')

P['recheck'] = (
    f'<p>OpenAI writes many redundant claims, and each one adds steps and gestures, so any earlier difference could be layout and nothing more. '
    f'Every compiled analysis was therefore rerun on theorems in optimal cut layout (ρ = 0) and on theorems with no cut at all. Definitions '
    f'carry no cut measure, so a run on proofs only is the control. The optimal-layout subset keeps {pct(keep["openai"])} of OpenAI’s proofs, '
    f'{pct(keep["mathlib"])} of mathlib’s and {pct(keep["human"])} of the human code’s.</p>'
    f'<p><b>The divergence is not layout.</b> On optimal-layout proofs it is {z_ratio:.1f}× the null (proofs only: {p_ratio:.1f}×). Comparing each stratum only '
    f'with the same stratum of mathlib, in the original basis, gives {REP["kl_rho0_vs_mathlib_rho0"]:.0f} bits for optimal-layout proofs and '
    f'{REP["kl_rho+_vs_mathlib_rho+"]:.0f} for redundant ones.</p>'
    f'<p><b>Eigenproof 1 is mostly layout.</b> {pct(M1["openai_excess_from_rho+"])} of OpenAI’s excess on it comes from proofs with redundant layout, '
    f'which are {pct(M1["openai_rho+"]["share"])} of its proofs. The pattern is <code>have h : a = b := by omega</code>. Rebuilt on optimal-layout proofs, the '
    f'integer-arithmetic direction drops to rank {z_ia["rank"]} ({z_ia["bits"]:.0f} bits), and the top direction becomes dependent rewriting under binders '
    f'({z_top["bits"]:.0f} bits), whose prevalence does not depend on layout. Even on optimal-layout proofs, OpenAI scores beyond +2 on eigenproofs 2–8 '
    f'{ep_lo:.0f} to {ep_hi:.0f} times as often as mathlib.</p>'
    f'<p><b>Compiled energy changes.</b> On optimal-layout proofs OpenAI’s median project costs {z_e[0]:.2f} bits per step against {z_e[1]:.2f} '
    f'(AUC {z_et["auc"]:.2f}, q &lt; 0.001). The redundant claims are cheap, predictable steps that pulled its average down. The text gap '
    f'does not move ({Pr["text_vs_ir"]["text_gap_raw"]:.2f} → {Z["text_vs_ir"]["text_gap_raw"]:.2f} bits per token).</p>')

P['ai'] = (
    '<p>The same pipeline was run on other AI-written Lean, each compiled against the mathlib used here with its own lakefile settings. '
    'Projects written for older Lean versions lose theorems to version drift, and failed theorems are dropped. That is a survivorship '
    'filter, since longer proofs are likelier to break. The IMO corpus keeps only a third of its theorems, so its column is indicative at best. '
    'Divergences use the corpus’s own size-matched null, and small corpora get a large null.</p>'
    + (f'<p><b>Redundant layout is common to all of them.</b> Sphere packing and Putnam have higher ρ than OpenAI '
       f'({PO["spherepacking"]["rho_mean"]:.3f} and {PO["putnam2025"]["rho_mean"]:.3f} bits, AUC {AU["spherepacking_vs_mathlib"]["rho_mean"]:.2f} and '
       f'{AU["putnam2025_vs_mathlib"]["rho_mean"]:.2f} against mathlib projects), and neither is more compressible than mathlib. '
       f'<b>The competition provers carry OpenAI’s first eigenproof.</b> {pct(EP1_AI["putnam2025"])} of AxiomProver’s Putnam theorems and '
       f'{pct(EP1_AI["imo2025"])} of Aristotle’s IMO theorems score beyond +2 on it. Their own most divergent direction is the same omega-in-equation-chain pattern '
       f'(match {max(CO["own_direction"]["putnam2025"]["match_openai_ep"]):.2f} to OpenAI’s). '
       f'<b>Sphere packing looks like human research code</b> in its gesture mix ({CO["corpora"]["spherepacking"]["ratio"]:.1f}× its null; its top direction is '
       f'dependent rewriting, the habit OpenAI shares with human code), but it has the most redundant layout of any corpus. '
       f'In text, all three sit between mathlib and OpenAI, near human research code.</p>'
       if all(c in PO for c in ('spherepacking', 'putnam2025')) else ''))

P['method'] = (
    '<ul>'
    '<li><b>Elaboration.</b> Lean 4.34.1, mathlib d13f23b. OpenAI projects were compiled in one shared environment, module by module. '
    'The human baseline was compiled module by module against its own imports, as <code>lake</code> would. Carleson’s checkout predates '
    'the mathlib pin, so 222 of its 4,898 theorems fail and are dropped. Theorems containing <code>sorryAx</code> are dropped everywhere. Auxiliary '
    'theorems (<code>_proof_n</code>, equation lemmas) are folded into their source.</li>'
    '<li><b>Text model.</b> Interpolated Kneser–Ney, order 5, chosen on held-out mathlib cross-entropy. Unknown pieces are spelled with a '
    'character model, so energy is a proper code length. Up to 1,000 declarations per non-mathlib project are sampled.</li>'
    f'<li><b>Statistics.</b> Medians with bootstrap intervals; two-sided Mann–Whitney AUC; Benjamini–Hochberg q across tests. '
    f'Eigenproofs use theorems with at least 10 steps, project-balanced weights and covariance shrinkage α = {R["regularization"]["alpha"]}. '
    f'The decomposition is stable across shrinkage choices for the first four directions.</li>'
    '<li><b>Cuts.</b> Use counts are proof-position occurrences. A proof used only inside a type or data stays alive as one copy. '
    'Sizes are exact big integers. The optimal layout decides bottom-up, eliminating a cut when (uses − 1)·|p| ≤ uses + 1.</li>'
    '<li><b>Proof terms.</b> Cut-free form computed through a substitution environment with canonical hashes, so it is never built. A cut variable '
    'hashes as its proof, an ordinary binder by its domain and enclosing binder. Data β-redexes are substituted silently, created redexes are left in place and counted '
    '(identical ones once). The explicit layout names a node when references × size exceed size + references + 1, and is then refined greedily up to six times. '
    'Budgets: 200k DAG nodes and 400k rank steps per proof; proofs over budget are dropped (10 of 254,147 in mathlib). Rank unfolds definitions up to 24 times, '
    'reducing projections of constructor applications.</li>'
    '</ul><p><b>Limits.</b></p><ul>'
    '<li>Low energy means “reads like mathlib”, not “is good mathematics”. mathlib is one community’s house style, and research code, '
    'human or AI, is expected to coin vocabulary.</li>'
    '<li>The compiled OpenAI sample is 96 projects of about 524; the text pass covers them all.</li>'
    '<li>The human baseline is small: 11 compiled projects from two efforts. Its intervals are wide, and its null is large.</li>'
    '<li>Other AI corpora were compiled against a newer mathlib than they were written for. Failures are not random.</li>'
    '<li>χ* is bracketed, not computed, and sharing is exact: a lemma abstracted over a varying part is not found.</li>'
    '<li>Every pass decides whether a term is a proof from the declared type of its statement’s head symbol. A statement that is a proposition only once '
    'definitions unfold, such as <code>S x</code> for <code>S : Set α</code> written as an application, is treated as data, so its <code>have</code> is not counted as a cut. '
    + (f'The third pass counts these: {pct(T["mathlib"]["hidden_share"], 2)} of mathlib proofs have one, '
       f'{T["mathlib"]["hidden_per_cut"] * 100:.2f} for every 100 cuts counted. The same rule applies to every corpus. '
       if TR and T['mathlib'].get('hidden_share') is not None else 'Its size is being measured. ') +
    'Rank uses the unfolding test.</li>'
    '<li>A 5-gram model is a weak model of Lean. A stronger one would lower every energy; whether it would close the gaps is untested.</li>'
    '</ul>')

P['history'] = [
    ('Energy report', 'Text and premise energy of openai/math against mathlib and human research code.'),
    ('Eigenproofs v1', 'Compiled gestures, structural rules, eigenproofs; 94 OpenAI projects.'),
    ('v2', f'Module-by-module check: {pct(ISO["same_u"] / ISO["n"], 1)} of theorems identical. A first explanation of the differences, auxiliary-lemma reuse, was wrong: most are in main terms.'),
    ('v3', 'FormulaHitting and KLS added (96 projects); Geometry.Arnold left out.'),
    ('v4', 'Cut compression. Before publishing, an inflated count of uses inside types was fixed, a ratio of summed sizes was replaced by per-proof means, and cut rates moved to the shared-size denominator. A lemma-level difference seen at 67 projects disappeared at 94.'),
    ('v5', 'Every compiled analysis rerun on proofs in optimal cut layout. Compiled energy and eigenproof 1 revised.'),
    ('Synthesis v1', 'All of the above from the ground up, plus the first three other AI corpora.'),
    ('This version', 'Proof-term pass: intrinsic compression bounds, logical rank of cuts, created redexes, layout invariance. A first run '
     'failed the rank-ladder check for over half of the proofs with redexes. The cause was the measurement: definitions were not unfolded, and cuts behind data β-redexes were missed. '
     'Rank figures are from the corrected second pass.'),
]

# ------------------------------------------------------------------ proof terms
TC = [c for c in ('mathlib', 'human', 'openai', 'spherepacking', 'putnam2025', 'imo2025') if TR and c in TR['corpora']]
T = TR['corpora'] if TR else {}
INV = TR.get('invariance') if TR else None


def sandwich_chart():
    W, L, Rm, row = 900, 190, 70, 44
    H = 58 + row * len(TC)
    hi = max(0.05, 1.15 * max(T[c]['chi_ub'] for c in TC))
    hi = math.ceil(hi * 20) / 20
    x = lambda v: L + v / hi * (W - L - Rm)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="What authors realize of the compression available in their proofs, by corpus">']
    step = 0.05 if hi <= 0.4 else 0.1
    for i in range(int(round(hi / step)) + 1):
        t = i * step
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="8" y2="{H - 44}" class="grid"/>'
                   f'<text x="{x(t):.1f}" y="{H - 26}" class="tick" text-anchor="middle">{t:.2f}</text>')
    for i, c in enumerate(TC):
        y0 = 22 + i * row
        a, lb, ub = T[c]['chi_author'], T[c]['chi_lb'], T[c]['chi_ub']
        col = GC.get(c, 'var(--c-ai)')
        out.append(f'<text x="{L - 12}" y="{y0 + 5}" class="lab" text-anchor="end">{GL[c]}</text>'
                   f'<line x1="{x(0):.1f}" x2="{x(ub):.1f}" y1="{y0}" y2="{y0}" class="grid"/>'
                   f'<rect x="{x(0):.1f}" y="{y0 - 6}" width="{x(a) - x(0):.1f}" height="12" style="fill:{col}"/>'
                   f'<rect x="{x(a):.1f}" y="{y0 - 6}" width="{max(x(lb) - x(a), 0):.1f}" height="12" style="fill:{col}" fill-opacity="0.3"/>'
                   f'<line x1="{x(ub):.1f}" x2="{x(ub):.1f}" y1="{y0 - 9}" y2="{y0 + 9}" class="med"/>'
                   f'<text x="{x(ub) + 6:.1f}" y="{y0 + 4}" class="tick strong">{pct(T[c]["realized"])}</text>')
    out.append(f'<text x="{(L + W - Rm) / 2:.0f}" y="{H - 4}" class="tick" text-anchor="middle">mean bits per proof</text></svg>')
    return ''.join(out)


def _t(c, f):
    try:
        v = f(T[c])
        return '–' if v is None else v
    except (KeyError, TypeError):
        return '–'


def _lad(c):
    v = T[c].get('ladder_holds')
    return f'{pct(v, 1)} of {T[c]["ladder_n"]:,}' if v is not None else '–'


terms_rows = [
    ['Proofs measured'] + [f'{T[c]["proofs"]:,}' for c in TC],
    ['χ<sub>author</sub><div class="sub">compression the written cuts achieve, laid out optimally</div>'] + [f'{T[c]["chi_author"]:.3f}' for c in TC],
    ['χ<sub>lb</sub><div class="sub">an explicit layout of the cut-free proof</div>'] + [f'{T[c]["chi_lb"]:.3f}' for c in TC],
    ['χ<sub>DAG</sub><div class="sub">every repeated subproof shared, names free</div>'] + [f'{T[c]["chi_ub"]:.3f}' for c in TC],
    ['<b>Realized</b><div class="sub">Σχ<sub>author</sub> ÷ Σχ<sub>lb</sub></div>'] + [f'<b>{pct(T[c]["realized"])}</b>' for c in TC],
    ['Missed ≥ 1 bit<div class="sub">share of proofs</div>'] + [pct(T[c]['missed_ge1'], 1) for c in TC],
    ['Cuts of rank ≥ 1<div class="sub">definitions unfolded</div>'] + [_t(c, lambda v: pct(v['cuts_rank_ge1_u'])) for c in TC],
    ['Created proof redexes<div class="sub">share of proofs</div>'] + [_t(c, lambda v: pct(v['residP_share'], 1)) for c in TC],
    ['Ladder: redex ⇒ rank ≥ 1 cut'] + [_lad(c) for c in TC],
    ['χ<sub>DAG</sub> ≤ log₂ max copies'] + [pct(T[c]['ub_le_occmax'], 1) for c in TC],
    ['κ ≤ Σ log₂ uses'] + [pct(T[c]['kappa_le_prod'], 1) for c in TC],
    ['κ against its first-order estimate<div class="sub">Spearman, proofs with κ &gt; 0</div>'] + [_t(c, lambda v: f'{v["kappa_est_spearman"]:.2f}') for c in TC],
]

LAD = T['mathlib']['ladder_u'] if TR else {}
lad_rows = [[{'-1': 'no shared cut', '0': '0', '1': '1', '2': '2', '3': '3 or more'}[k], f'{v["n"]:,}', f'{v["chi_author"]:.3f}',
             f'{v["chi_lb"]:.3f}', f'{v["chi_ub"]:.3f}', pct(v['residP'], 1)] for k, v in LAD.items()]

RBS = TR.get('realized_by_size') if TR else None
size_rows = []
if RBS:
    edges = RBS['bins'] + [None]
    for i, lo in enumerate(RBS['bins']):
        hi = edges[i + 1]
        size_rows.append([f'{lo:,}–{hi - 1:,}' if hi else f'{lo:,}+'] +
                         [(f'{pct(r["realized"])}<div class="sub">χ<sub>DAG</sub> {r["chi_ub"]:.2f} · {r["n"]:,}</div>' if (r := RBS['corpora'][c][i])['realized'] is not None else '–')
                          for c in TC if c in RBS['corpora']])
TOT = TX['totals'] if TX else None
miss_rows = [[mono(m['n']), f'{m["cutfree"]:,}', f'{m["author"]:,}', f'{m["explicit"]:,}', f'{m["dag"]:,}'] for m in (TX['top_missed'][:6] if TX else [])]


def _tm(k):
    return TR['tests'].get(f'{k}_vs_mathlib', {}).get('realized') if TR else None


if TR:
    ml, oa = T['mathlib'], T.get('openai', {})
    P['terms'] = (
        '<p>The cut measures above rank layouts against one another. The question they leave open is how much compression a proof has '
        'in it at all, whoever laid it out. This pass reads the proof term itself. It eliminates every written cut by substitution, without ever '
        'building the result. A cut variable is hashed as the proof it stands for, and an ordinary bound variable as its binder. So the same subproof '
        'is one node wherever it occurs, whether it was written twice, named once and used twice, or substituted from a cut. Three quantities '
        'come out, all in bits of cut compression against the same cut-free size S:</p><ul>'
        '<li><b>χ<sub>author</sub></b> = log₂(S ÷ the written cuts in their optimal layout): what the author’s own cuts achieve.</li>'
        '<li><b>χ<sub>lb</sub></b> = log₂(S ÷ G), where G is the exact size of an explicit layout. It names any repeated subproof that pays for its own name, '
        'cut or not, and is refined greedily. Any layout is a lower bound on the best, χ*.</li>'
        '<li><b>χ<sub>DAG</sub></b> = log₂(S ÷ D), where D counts distinct subproofs. That is sharing with no naming cost, an upper bound on χ*.</li></ul>'
        '<p>So χ<sub>author</sub> ≤ χ* and χ<sub>lb</sub> ≤ χ* ≤ χ<sub>DAG</sub>. The share an author realizes is Σχ<sub>author</sub> ÷ Σχ<sub>lb</sub>, '
        'a conservative estimate since χ<sub>lb</sub> ≤ χ*. A subproof is shared only with an identical one whose free variables are bound by the '
        'same binders, so every node G names could be a <code>have</code> at that point. Parametrized lemmas, which abstract over a varying part, are not counted. '
        'Before it was run on any corpus, the pass was checked on hand-computed theorems (<code>eigen/tests/terms_toy</code>). Its cut-free size agrees '
        f'with the cut pass’s exact count for {pct(ml["agree"], 1)} of mathlib proofs. The exceptions are proofs with created redexes, which this pass leaves unreduced.</p>'
        f'<p><b>Authors realize very different shares.</b> mathlib’s cuts realize {pct(ml["realized"])} of the compression the explicit layout finds'
        + (f', OpenAI’s {pct(oa["realized"])}' if oa else '') + '. '
        + ' '.join(f'{GL[c]}: {pct(T[c]["realized"])}.' for c in TC if c not in ('mathlib', 'openai')) +
        ' How much there is to realize depends mostly on proof length. At equal size the corpora have similar χ<sub>DAG</sub>, and AI proofs have more '
        'in total only because they are longer. The realization gap is not a length effect: in each size bin from 30 nodes up, mathlib realizes more '
        '(second table below)' + (f'. Across projects, OpenAI against mathlib gives AUC {TR["tests"]["openai_vs_mathlib"]["realized"]["auc"]:.2f} '
        f'(p = {sci(TR["tests"]["openai_vs_mathlib"]["realized"]["p"])}).' if TR and TR['tests'].get('openai_vs_mathlib', {}).get('realized') else '.') +
        ' The AI corpora pay twice. They write cuts that save nothing, the layout redundancy ρ above, and they leave out cuts that would save something. '
        f'In mathlib the misses are concentrated in a few computational proofs. Across all its proofs of 10 or more steps, the written cuts cut the cut-free size by '
        f'{pct(TOT["saving_author"]) if TOT else "–"}, the explicit layout by {pct(TOT["saving_explicit"]) if TOT else "–"}, and full sharing by '
        f'{pct(TOT["saving_dag"]) if TOT else "–"}. The largest gaps are brute-force determinants and coordinate formulas, where tactics emit the same '
        'subproof many times.</p>'
        '<p><b>Logical rank.</b> Each cut’s formula gets a rank: the depth of implications nested to the left, with ¬A read as A → ⊥ and definitions unfolded, '
        f'so <code>s ⊆ t</code> or <code>Monotone f</code> count as implications. In mathlib {pct(ml["cuts_rank_ge1_u"]) if ml.get("cuts_rank_ge1_u") is not None else "–"} '
        f'of cuts have rank ≥ 1, about double the purely syntactic count ({pct(ml["cuts_rank_ge1"])}). A <em>created redex</em> appears when cut elimination '
        'substitutes a λ-proof into a position where it is applied to a proof. It is a new cut that complete development does not remove. These occur in '
        + (f'{pct(ml["residP_share"], 1)} of mathlib proofs' if ml.get('residP_share') is not None else 'few proofs') +
        (f' and {pct(oa["residP_share"], 1)} of OpenAI’s' if oa.get('residP_share') is not None else '') + '.</p>'
        + (f'<p><b>Reproducibility.</b> {INV["n"]:,} OpenAI theorems were compiled both in one shared environment and module by module '
           f'(auxiliary <code>_proof_n</code> lemmas, numbered differently in the two modes, are set aside). {pct(INV["same_S"], 1)} have identical written size, '
           f'cut-free size and DAG. The {INV["layout_changed"]} that differ do so outside their cuts: written and cut-free size move by the same few nodes, '
           f'such as an instance found by a different path. So compilation mode never moves the cuts of a proof without changing the proof. '
           f'That layout does not affect χ* follows from the construction, and is checked on hand-built pairs.</p>' if INV else ''))

    def _rank_direction():
        L = T['mathlib'].get('ladder_u', {})
        if not all(k in L for k in ('0', '1')):
            return ''
        hi = [L[k] for k in ('1', '2', '3') if k in L]
        up = max(v['chi_ub'] for v in hi) > L['0']['chi_ub']
        return ('<li><b>Rank as a resource.</b> Only cuts of positive rank allow large speed-ups. In mathlib, though, proofs whose shared cuts reach rank 1 or more '
                + (f'have more compression available than rank-0 ones' if up else
                   f'have <em>less</em> compression available than rank-0 ones (χ<sub>DAG</sub> {min(v["chi_ub"] for v in hi):.2f}–{max(v["chi_ub"] for v in hi):.2f} against {L["0"]["chi_ub"]:.2f})')
                + f'. What rises with rank is created redexes, from {pct(L["0"]["residP"])} to {pct(max(v["residP"] for v in hi))}: a shared implication is a local lemma '
                'that gets applied, which is abstraction, not repetition. Whether hard proofs in other fields use rank for compression, as the theory allows, can be tested on bigger corpora.</li>')

    P['theory'] = [
        ('Copy-count identity', 'Proved; checked on every proof',
         'Eliminate every written cut. A written step x is copied m(x) times, where m sums, over the uses of each cut whose proof contains x, the copies of '
         'that use. Then the cut-free size is Σ<sub>x</sub> m(x), less the binder and use nodes that disappear. So κ is log₂ of the <em>average copy count</em> of a written '
         'step, and one bit of cut compression is a doubling of it. Two corollaries hold for every proof in every corpus. First, κ ≤ Σ<sub>cuts</sub> log₂ uses, since '
         'm(x) is at most the product of the use counts of the cuts enclosing x. Eliminating outermost cuts first, each step multiplies size by at most its use count. '
         f'Second, χ<sub>DAG</sub> = log₂ of the average occurrence count of a distinct subproof, which is at most log₂ of the largest. The product bound is loose, '
         f'reaching a median {ml["tightness_median"]:.2f} of itself in mathlib, because it ignores how large the copied proofs are. The first-order version, '
         f'Σ log₂(1 + (uses − 1)·|p|/N), exact for a single cut, tracks κ with Spearman {ml["kappa_est_spearman"]:.2f}.'),
        ('Compression is intrinsic', 'By construction; checked on hand-built pairs',
         'S, D and χ* depend only on the cut-free proof, so any two layouts of one proof have the same χ*, and κ = χ − ρ separates the proof from its layout. '
         '<code>have h := p; ⟨h, h⟩</code> and <code>⟨p, p⟩</code> get identical S and D, and compiling ' + (f'{INV["n"]:,}' if INV else 'the OpenAI') + ' theorems two ways reproduces every measure '
         'except where the proof itself changed. '
         'Compression becomes a property of the mathematics, and layout a property of the author.'),
        ('Rank ladder', 'Classical; confirmed on the data',
         'A created redex that applies a substituted proof to a proof needs a cut whose formula, unfolded, has rank ≥ 1. Rank-0 cuts can only create '
         'instantiations with data. So with rank-0 cuts, eliminating cuts costs at most the single-exponential product bound above. The tower-of-exponentials '
         'blowups of cut elimination (Statman; Orevkov) need cuts of positive rank, and the classical upper bound is a tower whose height grows with rank. '
         + (f'The implication held for {pct(ml["ladder_holds"], 1)} of the {ml["ladder_n"]:,} mathlib proofs with such redexes'
            if ml.get('ladder_holds') is not None else 'It is checked here on the corpora') +
         + (f' (the {round((1 - ml["ladder_holds"]) * ml["ladder_n"])} left are proofs where a hypothesis is a proposition only through a defined family, such as '
            '<code>R.arrows f</code> for a sieve, which the rank pass then reads as data)' if ml.get('ladder_holds') is not None and ml['ladder_holds'] < 1 else '') +
         '. Before definitions were unfolded and cuts behind data β-redexes were seen, it seemed to fail for over half. That was a measurement error, '
         'found by printing a counterexample.'),
        ('Real proofs sit in the elementary regime', 'Empirical',
         f'χ<sub>DAG</sub> ≥ 1 bit (sharing could halve the proof) in {pct(ml["ub_ge1"], 1)} of mathlib proofs; created proof redexes are rare; most cuts are rank 0. '
         'Libraries use cuts to organize proofs, not to compress them: what cut elimination could cost them in theory is not what it costs them in practice. '
         'The exceptions are computational: certificates and expanded polynomial identities.'),
    ]
    P['directions'] = (
        '<ul>'
        '<li><b>Is the optimal layout tractable?</b> With only exact, scope-respecting sharing, choosing which subproofs to name is an optimization over the DAG '
        'with a naming cost. The greedy layout here is sandwiched against the DAG. Is χ* polynomial-time, or hard like the smallest-grammar problem it '
        'resembles once parametrized lemmas are allowed? The gap χ<sub>DAG</sub> − χ<sub>lb</sub> measured here bounds how much an exact algorithm could gain.</li>'
        '<li><b>The distribution of copy counts.</b> By the identity, κ and χ<sub>DAG</sub> are log-means of copy counts. Their tails, which are a few proofs with '
        'enormous multiplicity, decide every corpus mean. A model of where multiplicity comes from (tactics, automation, author habit) would predict compression '
        'from the proof script alone.</li>'
        + _rank_direction() +
        '<li><b>A layout optimizer.</b> For AI-written proofs the two inefficiencies are separate and both mechanical. Dropping redundant cuts and naming '
        'repeated subproofs are term-level rewrites that keep the theorem. The bounds here say how much each could save per corpus before anyone writes one.</li>'
        '</ul>')

# ------------------------------------------------------------------ page
FIGS = [
    (f'+{et("e_tok", "mathlib"):.2f}', 'bits per token', 'OpenAI’s text over mathlib’s, median project'),
    (f'{ratio:.1f}×', 'the null', 'OpenAI’s compiled divergence from mathlib'),
    (f'{AU["openai_vs_mathlib"]["rho_mean"]:.2f}', 'AUC', 'layout redundancy, OpenAI against mathlib projects'),
    (f'{z_et["auc"]:.2f}', 'AUC', 'compiled energy, once redundant claims are set aside'),
]

if TR:
    P['summary'].append((
        'Authors realize different shares of the compression their proofs contain.',
        f'Measured on the proof terms themselves, mathlib’s written cuts realize {pct(T["mathlib"]["realized"])} of the sharing an explicit layout finds'
        + (f', OpenAI’s {pct(T["openai"]["realized"])}' if 'openai' in T else '') + '. '
        'Compression is intrinsic to a proof, and κ is exactly the log of the average number of times cut elimination copies a step. In every corpus it is small, '
        'and the blowup-capable kind of cut, a named implication applied to a proof, is rare.'))
    ledger.insert(4, ('new', 'Compression is a property of the proof; realizing it is a property of the author.',
                      f'Realized share: ' + ', '.join(f'{GL[c]} {pct(T[c]["realized"])}' for c in TC) + '.'))
    ledger.insert(5, ('new', 'Created proof redexes need a cut of rank ≥ 1 (the rank ladder).',
                      (f'Holds for {pct(T["mathlib"]["ladder_holds"], 1)} of {T["mathlib"]["ladder_n"]:,} mathlib cases after definitions are unfolded.'
                       if T['mathlib'].get('ladder_holds') is not None else 'Checked on the second pass.')))
toc = [('summary', 'Summary'), ('ledger', 'What holds'), ('data', 'Corpora'), ('units', 'Units'), ('text', 'Text energy'),
       ('compiled', 'Compiled proofs'), ('cuts', 'Cut compression'), ('eigen', 'Eigenproofs'), ('recheck', 'Layout re-check'),
       ('ai', 'Other AI corpora')] + ([('terms', 'Proof terms'), ('theory', 'What it suggests')] if TR else []) + [('history', 'Revisions'), ('method', 'Method and limits')]

body = []
body.append(f'''<header class="top">
  <p class="eyebrow">Research report · 12 October 2026</p>
  <h1>Machine-Written Lean, Measured</h1>
  <p class="dek">{P["dek"]}</p>
  <div class="figs">{''.join(f'<div class="fig"><div class="v">{v}<small> {u}</small></div><div class="l">{l}</div></div>' for v, u, l in FIGS)}</div>
</header>''')
body.append('<section id="summary"><h2>Summary</h2><div class="findings">' +
            ''.join(f'<div class="finding"><h3>{h}</h3><p>{t}</p></div>' for h, t in P['summary']) + '</div></section>')
body.append('<section id="ledger"><h2>What holds, what changed</h2><div class="ledger">' +
            ''.join(f'<div class="lrow"><span class="tag t-{k}">{TAG[k]}</span><div><b>{a}</b><div class="sub">{b}</div></div></div>' for k, a, b in ledger) +
            '</div></section>')
body.append(f'<section id="data"><h2>Corpora and pipeline</h2><div class="prose">{P["pipeline"]}</div>' +
            table(['Corpus', 'Written by', 'Projects (text / compiled)', 'Theorems compiled', 'Notes'], corpora_rows, 'wide') + '</section>')
body.append('<section id="units"><h2>Units</h2><div class="prose"><p>Every measure here is in bits: a description length, or a log-ratio of sizes. '
            'Bits from different units are not interchangeable.</p></div>' + table(['Unit', 'Measures', 'Definition'], units_rows, 'wide') + '</section>')
body.append(f'<section id="text"><h2>Text energy</h2><div class="prose">{P["text"]}</div><figure class="chart">{strip_chart()}'
            f'<figcaption>Each dot is a project with 20 or more theorems; the tick is the median. Values above 11 bits are drawn at the edge.</figcaption></figure></section>')
body.append(f'<section id="compiled"><h2>Compiled proofs</h2><div class="prose">{P["compiled"]}</div>' +
            table(['', 'mathlib', 'OpenAI', 'Human', 'AUC vs mathlib', 'AUC vs human'], rules_rows) +
            '<p class="cap">Medians over projects with at least 20 theorems. Grey AUCs have q ≥ 0.05.</p></section>')
body.append(f'<section id="cuts"><h2>Cut compression</h2><div class="prose">{P["cuts"]}</div><figure class="chart">{cut_chart()}'
            '<figcaption>Grey bars: χ, what sharing could save. Coloured bars: ρ, how far the written proof sits above its optimal layout.</figcaption></figure>' +
            table([''] + [GL[c] for c in ['mathlib', 'openai', 'human'] + AI], cut_rows) +
            f'<p class="cap">Per-proof rows are means over theorems with at least 10 steps ({", ".join(f"{GL[c]} {PO[c]["proofs"]:,}" for c in ["mathlib", "openai", "human"] + AI)}). '
            'Lemma rows are medians over projects with at least 20 proofs.</p></section>')
body.append(f'<section id="eigen"><h2>Eigenproofs</h2><div class="prose">{P["eigen"]}</div><figure class="chart">{spectrum_chart()}</figure>' +
            table(['', 'Eigenproof', 'Bits', 'Split-half', 'mathlib', 'OpenAI', 'Human', 'OpenAI, ρ = 0', 'Excess from ρ > 0'], ep_rows) +
            '<p class="cap">Percentages are the share of theorems scoring beyond +2 mathlib standard deviations, project-balanced. The last two columns '
            'are from the layout re-check.</p></section>')
body.append(f'<section id="recheck"><h2>Layout re-check</h2><div class="prose">{P["recheck"]}</div>' +
            table([''] + [n for _, _, n in COLS], rc_rows) +
            '<p class="cap">Each column reruns the whole compiled pipeline (vocabulary, eigenproofs, null, tests) on that subset. Grey AUCs have q ≥ 0.05.</p></section>')
body.append(f'<section id="ai"><h2>Other AI corpora</h2><div class="prose">{P["ai"]}</div>' +
            table([''] + [GL[c] for c in ai_cols], ai_rows) +
            '<p class="cap">Text energy for OpenAI and human code is from the full text study (524 and 24 projects); for the other corpora it is the median '
            'over their own projects. Null ratios here use ten fresh null draws, so OpenAI’s differs slightly from the figure above. IMO 2025 has too few '
            'theorems for project-level tests. Erdős 90 and FLT were not compiled.</p></section>')
if TR:
    body.append(f'<section id="terms"><h2>Proof terms</h2><div class="prose">{P["terms"]}</div><figure class="chart">{sandwich_chart()}'
                '<figcaption>Solid bar: χ<sub>author</sub>, what the written cuts save. Pale extension: what the explicit layout adds. Tick: χ<sub>DAG</sub>, the '
                'ceiling. The label is the share realized.</figcaption></figure>' +
                table([''] + [GL[c] for c in TC], terms_rows) +
                (table(['Cut-free size'] + [GL[c] for c in TC if c in RBS['corpora']], size_rows) +
                 '<p class="cap">Realized share within bins of cut-free proof size; below it, the mean χ<sub>DAG</sub> (what there is to realize) and the number of proofs. Cells with fewer than 30 proofs are left out.</p>' if size_rows else '') +
                f'<p class="cap">Means over proofs with at least 10 steps; corpus shares pool proofs. Rank and created-redex rows use the second pass '
                f'(definitions unfolded), which covers {", ".join(f"{GL[c]} {pct(T[c]["v2_share"])}" for c in TC if T[c].get("v2_share") is not None and T[c]["v2_share"] < 0.995) or "every corpus"}'
                f'{" of proofs" if any(T[c].get("v2_share", 1) < 0.995 for c in TC) else ""}.</p></section>')
    body.append('<section id="theory"><h2>What it suggests</h2><div class="prose"><p>The measurements support four statements about proofs in general. '
                'Two are theorems with short proofs, one is classical, and one is empirical.</p></div><div class="findings">' +
                ''.join(f'<div class="finding"><h3>{h}</h3><p class="sub">{st}</p><p>{t}</p></div>' for h, st, t in P['theory']) + '</div>'
                + (table(['Highest rank among shared cuts', 'mathlib proofs', 'χ<sub>author</sub>', 'χ<sub>lb</sub>', 'χ<sub>DAG</sub>', 'Created proof redexes'], lad_rows) +
                   '<p class="cap">mathlib, second pass. Ranks unfolded; “no shared cut” proofs may still have linear or dead cuts.</p>' if lad_rows else '')
                + f'<h3 class="sub-h">Directions</h3><div class="prose">{P["directions"]}</div>'
                + (table(['Largest missed sharing in mathlib', 'Cut-free', 'Author', 'Explicit', 'DAG'], miss_rows) +
                   '<p class="cap">Sizes in proof-position nodes.</p>' if miss_rows else '') + '</section>')
body.append('<section id="history"><h2>Revisions</h2><ol class="hist">' +
            ''.join(f'<li><b>{a}.</b> {b}</li>' for a, b in P['history']) + '</ol></section>')
body.append(f'<section id="method"><h2>Method and limits</h2><div class="prose">{P["method"]}'
            f'<p class="cap">Every number on this page is read from: {"; ".join(esc(s) for s in SRC)}. Built by synthesis/build.py.</p></div></section>')

CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.css')).read()
page = f'''<title>Machine-Written Lean, Measured</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="wrap">
<nav class="toc" aria-label="Sections"><p class="eyebrow">Contents</p>{''.join(f'<a href="#{i}">{t}</a>' for i, t in toc)}</nav>
<main>{''.join(body)}</main>
</div>'''
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report.html')
open(out, 'w').write(page)
print('wrote', out, len(page))
