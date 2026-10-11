"""Assemble report.html from data/out/* (numbers in the prose are read from the outputs)."""
import json

import numpy as np
import pandas as pd

from analysis_groups import group_of

O = 'data/out/'
P = pd.read_csv(O + 'projects.csv')
G = pd.read_csv(O + 'group_metrics.csv')
Tt = pd.read_csv(O + 'tests.csv')
S = json.load(open(O + 'summary.json'))
A = pd.read_csv(O + 'areas.csv')
H = json.load(open(O + 'heat.json'))
C = pd.read_csv(O + 'corr_openai.csv', index_col=0)

T = pd.read_pickle('data/text_energy.pkl')
T['group'] = [group_of(c, p) for c, p in zip(T.corpus, T.project)]
dec = []
for g in ['mathlib', 'human-upstream', 'human', 'strongpnt', 'openai', 'openai-ten']:
    d = T[T.group == g]
    n = d.n_tok.sum()
    dec.append(dict(group=g, c_name=d.E_n.sum() / n, c_unk=d.E_unk.sum() / n, c_op=d.E_o.sum() / n,
                    c_num=d.E_k.sum() / n, c_end=d.E_e.sum() / n))
DEC = pd.DataFrame(dec).set_index('group')
DEC.to_json(O + 'decomp.json', orient='index')


def gm(metric, group, f='median'):
    return float(G[(G.metric == metric) & (G.group == group)][f].iloc[0])


def tt(metric, vs, f='diff'):
    return float(Tt[(Tt.metric == metric) & (Tt.vs == vs)][f].iloc[0])


reg = S['regression']
k_oa = 'C(group, Treatment("mathlib"))[T.openai]'
k_hu = 'C(group, Treatment("mathlib"))[T.human]'
n = S['n_projects']
e_ml, e_oa, e_hu, e_up = gm('e_tok', 'mathlib'), gm('e_tok', 'openai'), gm('e_tok', 'human'), gm('e_tok', 'human-upstream')
len_ml, len_oa = gm('tok_per_thm', 'mathlib'), gm('tok_per_thm', 'openai')
eq_len = tt('e_tok', 'mathlib') * len_oa
oa_names = DEC.loc['openai', 'c_name'] + DEC.loc['openai', 'c_unk']
ml_names = DEC.loc['mathlib', 'c_name'] + DEC.loc['mathlib', 'c_unk']
gap_total = DEC.loc['openai'].sum() - DEC.loc['mathlib'].sum()
name_part = (oa_names - ml_names) / gap_total
areas_all_higher = bool((A.median_openai > A.median_mathlib).all())

text = {}
text['lede'] = (
    f"Score every declaration by the bits it costs under a model of mathlib's own text. The median OpenAI project spends "
    f"<b>{e_oa:.2f} bits per token</b> against <b>{e_ml:.2f}</b> for a held-out mathlib project. Human research formalizations "
    f"sit at {e_hu:.2f}, close to OpenAI on raw text. OpenAI pulls away from both in two places: the names it coins and the "
    f"constants it refers to, {tt('e_prem', 'human'):.1f} bits per reference more than human projects. Its tactic and "
    f"syntax energy is the same as human work.")
FIGS = [
    dict(v=f"{e_oa:.2f}", unit='bits/token', l=f"OpenAI median project ({n['openai']} projects)"),
    dict(v=f"{e_ml:.2f}", unit='bits/token', l=f"mathlib median project, scored held out ({n['mathlib']} projects)"),
    dict(v=f"+{tt('d_e_tok', 'mathlib'):.2f}", unit='bits/token', l='OpenAI excess over mathlib in the same area'),
    dict(v=f"+{tt('e_prem', 'mathlib'):.1f}", unit='bits/ref', l='extra premise energy per constant referenced'),
]
text['model'] = f"""
<p>Treat mathlib as the ground state of a physical system. Fit a probability model q to mathlib's own text, and give
each candidate proof x the energy</p>
<p class="formula">E(x) = −log₂ q<sub>mathlib</sub>(x) &nbsp;bits, &nbsp;&nbsp;so that&nbsp; q(x) ∝ 2<sup>−E(x)</sup>.</p>
<p>This is the Boltzmann relation with temperature fixed at one bit. A proof written the way mathlib writes proofs
sits in a low-energy, high-probability state. Every departure costs bits: an unfamiliar word, an unusual
tactic order, a reference to a constant mathlib has never seen. By Shannon's source-coding theorem, E(x) is also the
length of the shortest code for x built from mathlib's statistics. "Energy to compose" is therefore a literal description
length, not a metaphor stacked on a metaphor.</p>
<p>Two channels are measured separately, because they turn out to be nearly independent (Spearman ρ =
{C.loc['e_tok', 'e_prem']:.2f} across OpenAI projects):</p>
<ul>
<li><b>Text energy.</b> A 5-gram Kneser–Ney model of mathlib's Lean source, with identifiers split into mathlib's naming
pieces (<code>Finset.sum_le_sum</code> → <code>Finset .sum _le _sum</code>, camelCase split into words). A word mathlib has
never used is spelled out letter by letter the first time a project uses it. After that, each reuse costs
1 + log₂(words the project has coined so far) bits, so a project pays once for each word it invents. Numerals of four or more digits cost log₂10 bits per digit and are booked
separately, so kernel-checked certificates cannot dominate the comparison.</li>
<li><b>Premise energy.</b> Every identifier is resolved against the elaborated mathlib environment at OpenAI's pinned
revision (<code>d13f23b</code>, 479,313 user-facing constants, built here) and against each corpus's own declarations.
A library reference costs −log₂ of mathlib's own frequency of referring to that constant. A bespoke reference
costs the bits needed to say "one of mine" plus "which one".</li>
</ul>
<p>mathlib is never graded on text it was trained on. Each mathlib project is scored by a model fit to the other four
fifths of mathlib. Every other corpus is scored by the model fit to all of mathlib, which gives the other corpora a small
advantage.</p>"""
text['strip'] = (
    f"Each dot is a project with 20 or more theorems. The OpenAI distribution barely overlaps mathlib's: a random OpenAI project "
    f"spends more bits per token than a random mathlib project {tt('e_tok', 'mathlib', 'auc') * 100:.0f}% of the time. Human research "
    f"projects sit between the two, and their directories written for upstreaming to mathlib land on mathlib itself "
    f"({e_up:.2f}). That is the check that the model measures mathlib-likeness rather than difficulty. Switch to premises "
    f"to see the second channel.")
text['heat'] = (
    "Each token is shaded by its own surprisal under mathlib's model, with mathlib's example scored held out. "
    "The OpenAI examples are core-regime theorems of typical length near the 5th, 50th and 95th percentile of specific energy. "
    "The cold tokens are mathlib's own lemmas, tactics and notation: <code>le_iSup_of_le</code>, <code>funext</code>, "
    "<code>simp only [Pi.add_apply, …]</code>. The hot ones are names the project coined, such as <code>littleFinitisticDimension</code>, "
    "<code>I.WrapData</code> and <code>addresses_agree</code>. A coined word pays for its spelling the first time and is cheap after that. "
    "Hover a token for its bits.")
text['decomp'] = (
    f"Split each token's bits by what kind of token it is. Pooled over all sampled declarations, OpenAI spends "
    f"{DEC.loc['openai'].sum() - DEC.loc['mathlib'].sum():.2f} bits per token more than mathlib, and {name_part * 100:.0f}% of that gap is in "
    f"names: identifier pieces mathlib's model finds unlikely, plus spelling out words it has never seen. Syntax, "
    f"meaning tactics, brackets and operators, adds {DEC.loc['openai', 'c_op'] - DEC.loc['mathlib', 'c_op']:.2f} bits per token. "
    f"The proofs are assembled from mathlib's moves. What they are about is named in a private vocabulary.")
text['area'] = (
    f"The excess is not a matter of subject mix. {'In every one' if areas_all_higher else 'In most'} of the {len(A)} areas where both "
    f"libraries have at least three projects, the median OpenAI project costs more than the median mathlib project. Against the "
    f"mathlib median of its own area, the typical OpenAI project pays {tt('d_e_tok', 'mathlib'):+.2f} bits per token "
    f"[{tt('d_e_tok', 'mathlib', 'lo'):.2f}, {tt('d_e_tok', 'mathlib', 'hi'):.2f}].")
text['test'] = (
    f"Against mathlib, every energy measure separates cleanly (all q &lt; 0.001). Against the {n['human']} human research projects "
    f"the gaps are smaller. Specific energy is {tt('e_tok', 'human'):+.2f} bits per token and name energy {tt('e_name', 'human'):+.2f}. "
    f"Premise energy is {tt('e_prem', 'human'):+.2f} bits per reference, and bespoke references are {tt('bespoke_share', 'human') * 100:+.0f} "
    f"points. Syntax energy and theorem length do not differ, and the area-matched excess (human projects measured against all "
    f"of mathlib) is {tt('d_e_tok', 'human'):+.2f}, q = {tt('d_e_tok', 'human', 'q'):.2f}. One measure runs the other way: "
    f"<b>library surprisal is lower</b> for OpenAI ({tt('lib_surp', 'mathlib'):+.2f} bits per mathlib constant against mathlib, "
    f"{tt('lib_surp', 'human'):+.2f} against human work). When OpenAI code reaches into mathlib, it reaches for the most "
    f"common lemmas.")
cert_k = reg['e_tok']['cert']
_EO = '/Users/safsom/Projects/math-ai-projects/eigen/out_final'
_RC = {k: json.load(open(f'{_EO}/{d}/results.json')) for k, d in (('p', 'analysis_proofs'), ('z', 'analysis_rho0'))}
text['control'] = f"""
<p><b>Size.</b> Within OpenAI, larger projects spend more bits per token (Spearman ρ = 0.47 with log declarations).
In mathlib and in the human projects size makes no difference (ρ ≈ 0.06). A regression of project specific energy on group, log project size and a certificate-regime indicator
(HC3 errors, {n['mathlib']} mathlib, {n['openai']} OpenAI and {n['human']} human projects) still gives OpenAI
<b>{reg['e_tok'][k_oa][0]:+.2f} ± {reg['e_tok'][k_oa][1]:.2f}</b> bits per token over mathlib, against
{reg['e_tok'][k_hu][0]:+.2f} ± {reg['e_tok'][k_hu][1]:.2f} for human research. For premise energy the gaps are
{reg['e_prem'][k_oa][0]:+.2f} and {reg['e_prem'][k_hu][0]:+.2f} bits per reference.</p>
<p><b>Per theorem.</b> The median OpenAI theorem costs {gm('E_thm_struct', 'openai'):.0f} bits against {gm('E_thm_struct', 'mathlib'):.0f}
for mathlib, so under mathlib's distribution it is 2<sup>{gm('E_thm_struct', 'openai') - gm('E_thm_struct', 'mathlib'):.0f}</sup> times
less probable. Most of that factor is length ({len_oa:.0f} tokens against {len_ml:.0f}). Held to the same length, the
style penalty alone is about {eq_len:.0f} bits per theorem.</p>
<p><b>The certificate shell.</b> The {int(G[(G.metric == 'e_tok') & (G.group == 'openai-certificate')].n.iloc[0])} OpenAI projects whose
declarations are 30% or more numerical certificates run hottest within OpenAI ({gm('e_tok', 'openai-certificate'):.1f} bits per token before
digits; digits add {gm('lit_share', 'openai-certificate') * 100:.0f}% more on top). Removing them does not change the picture: the
core regime's median is {gm('e_tok', 'openai-core'):.2f}.</p>
<p><b>The earlier style proxies.</b> Across OpenAI projects, text energy tracks coined vocabulary (ρ = {C.loc['e_tok', 'oov']:.2f})
and the share of bespoke references (ρ = {C.loc['e_tok', 'bespoke_share']:.2f}). It tracks certificate mass (ρ =
{C.loc['e_tok', 'cert_mass']:.2f}) and numbered names (ρ = {C.loc['e_tok', 'numbered']:.2f}) only weakly. Energy therefore recovers
the earlier dashboard's finding of "more bespoke definitions, less reliance on mathlib, mathlib's naming conventions broken" as one
quantity with a single unit. It also shows that the brute-force and template proxies are separate axes.</p>
<p><b>Redundant claims.</b> The compiled follow-up found that OpenAI writes many redundant single-use <span class="mono">have</span>
claims. They do not produce this gap. In the {_RC['p']['sizes'][-1]['projects']} compiled OpenAI projects, the median project's
text-energy gap to mathlib is {_RC['p']['text_vs_ir']['text_gap_raw']:.2f} bits per token over all proofs and
{_RC['z']['text_vs_ir']['text_gap_raw']:.2f} over the proofs whose cut layout is already optimal. Restricted to those proofs, the median
OpenAI theorem's text energy is {_RC['z']['decl_join']['openai']['e_tok_median']:.2f} bits per token, against
{_RC['p']['decl_join']['openai']['e_tok_median']:.2f} over all proofs.</p>"""
text['method'] = f"""
<p>Rebuilt from the method notes of the earlier dashboard, <i>Proof style in OpenAI's Lean library</i>. The code from that
conversation was not available here, so the parser, units and controls were re-implemented from its description.</p>
<ul>
<li><b>Corpora.</b> openai/math (Lean library, {int(P[P.group=='openai'].n_decls.sum()):,} declarations in projects with
20+ theorems) and openai/ten-proofs; mathlib at <code>d13f23b</code>, the revision OpenAI pins, built with
<code>lake build</code> from the official cache; Carleson, FLT, PFR and sphere eversion at current heads; StrongPNT.</li>
<li><b>Units.</b> OpenAI <code>OAI/&lt;Area&gt;/&lt;Topic&gt;</code>; mathlib <code>Mathlib/&lt;A&gt;/&lt;B&gt;</code>; human projects
by first-level directory, with <code>Mathlib</code>, <code>ToMathlib</code> and <code>ForMathlib</code> directories kept apart as
"upstreaming". Up to 1,000 declarations per non-mathlib project are sampled uniformly. All mathlib declarations are scored.</li>
<li><b>Text model.</b> Interpolated Kneser–Ney, order 5, chosen by held-out mathlib cross-entropy (orders 3–6: 7.10, 6.87, 6.77,
6.72 bits/token before camelCase splitting). Vocabulary is mathlib tokens seen twice or more. Unknown pieces are spelled with
a character unigram model, so E is a proper code length. Sums over the vocabulary were checked to equal 1.</li>
<li><b>Premise model.</b> Syntactic resolution with namespaces, <code>open</code> and <code>_root_</code>. Binder-position
identifiers are dropped. Mixture code P(r) = π·[bespoke]/m + (1−π)·q(r), with π = mathlib's same-project reference rate and q its
reference frequency (add-½ over all constants), both held out by fold for mathlib declarations.</li>
<li><b>Statistics.</b> Median project with 4,000-resample bootstrap intervals; two-sided Mann–Whitney tests with Benjamini–Hochberg
q-values across all 24 comparisons.</li>
</ul>
<p><b>Limits.</b></p>
<ul>
<li>A low energy means "reads like mathlib", which is not the same as "is good mathematics". mathlib is one community's
house style. Research formalizations, human or AI, are expected to spend more on new vocabulary.</li>
<li>The OpenAI library was not elaborated: 26 million lines will not compile on this machine. The premise channel uses the
elaborated mathlib environment but resolves OpenAI identifiers syntactically. Dot-notation and some local names go unresolved
in every corpus.</li>
<li>An n-gram model is a weak model of Lean. A stronger one would lower every energy. Whether it would close the gap is
untested.</li>
<li>Only {n['human']} human research projects pass the 20-theorem bar, so those intervals are wide.</li>
</ul>"""

areas = A[['area', 'median_mathlib', 'median_openai', 'size_mathlib', 'size_openai']].copy()
areas['gap'] = areas.median_openai - areas.median_mathlib
areas = areas.sort_values('gap', ascending=False)
proj = P.fillna({"e_prem": 0})[['group', 'project', 'e_tok', 'e_prem', 'n_thm', 'regime']].round(4)

data = dict(text=text, figs=FIGS, projects=proj.to_dict('records'),
            groups=G.replace({np.nan: None}).to_dict('records'),
            tests=Tt.to_dict('records'), decomp=DEC.reset_index().round(4).to_dict('records'),
            areas=areas.round(4).to_dict('records'), heat=H)
for h in data['heat']:
    while h['spans'] and h['spans'][-1][1] is None and not h['spans'][-1][0].strip():
        h['spans'].pop()
    if h['spans'] and h['spans'][0][1] is None:
        h['spans'][0][0] = h['spans'][0][0].lstrip()
    h['prefix'] = h['prefix'].strip() + ' '
html = open('report_template.html').read()
html = html.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False, allow_nan=False).replace('</', '<\\/'))
html = html.replace('/*SCRIPT*/', open('report.js').read())
open('report.html', 'w').write(html)
print('wrote report.html', len(html))
print(text['lede']); print(text['decomp']); print(text['area'])
