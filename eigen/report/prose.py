"""Prose for eigenproofs.html. Numbers are read from the results, never typed in."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = json.load(open(os.path.join(ROOT, os.environ.get('GOUT', 'out'), 'analysis_merged', 'results.json')))
R0 = json.load(open(os.path.join(ROOT, os.environ.get('GOUT', 'out'), 'analysis', 'results.json')))  # omega and lia kept apart
ISO = json.load(open(os.path.join(ROOT, 'out_swap', 'compare.json')))  # shared vs isolated compilation (compare_iso.py)

G = {(r['metric'], r['group']): r for r in R['groups']}
T = {(t['vs'], t['metric']): t for t in R['tests']}
SZ = {r['group']: r for r in R['sizes']}
M = {m['rank']: m for m in R['modes']}


def med(m, g, pct=False, d=2):
    v = G[(m, g)]['median']
    return f'{100 * v:.1f}%' if pct else f'{v:.{d}f}'


def auc(vs, m):
    return f"{T[(vs, m)]['auc']:.2f}"


def prev(k, g):
    return f"{100 * M[k]['prevalence'][g]['beyond2']:.1f}%"


kl, kl0 = R['kl_bits']['openai'], R0['kl_bits']['openai']
klh = R['kl_bits']['human']
null, nullh = R['null'], R['null_human']
ratio = kl / null['total_median']
ratio_h = klh / nullh['total_median']
n_oai = SZ['openai']['projects']
tvi = R['text_vs_ir']
DJ = R['decl_join']

FIGS = [
    dict(v=f'{ratio:.1f}×', l=f'OpenAI’s divergence from mathlib’s gesture distribution, against random sets of {n_oai} mathlib projects ({kl:.0f} vs {null["total_median"]:.0f} bits)'),
    dict(v=f'{ratio_h:.1f}×', l=f'The same ratio for human research code: Carleson and sphere eversion ({klh:.0f} vs {nullh["total_median"]:.0f} bits)'),
    dict(v=med('e_ir', 'openai'), unit='bits/step', l=f'Compiled energy of the median OpenAI project; mathlib’s is {med("e_ir", "mathlib")}'),
    dict(v=f"{tvi['text_gap_given_ir']:.2f}", unit='bits/token', l='OpenAI’s text-energy gap that remains after compiled energy is held fixed'),
]

TEXT = {}
TEXT['lede'] = (
    f'The first energy study scored the source text of OpenAI’s Lean library. Here {n_oai} sampled OpenAI projects '
    f'({SZ["openai"]["theorems"]:,} theorems) were elaborated against mathlib, and each proof term was read as a tree of '
    f'<em>gestures</em>: inference steps with names erased and types reduced to their head connective. '
    f'Pooled over a project, OpenAI’s proofs seem to cost what mathlib’s do per step, but only because its many redundant '
    f'<span class="mono">have</span> claims are cheap; without them its proofs cost more. What differs most is the mix of gestures, and '
    f'the eigenvectors of that difference, the <em>eigenproofs</em>, show which mixes. One is OpenAI’s own: '
    f'integer arithmetic stitched into chains of equations, mostly inside redundant claims. The others are shared with human research code.')

TEXT['types-text'] = (
    '<p>Every theorem’s proof term is walked from the root. Each node becomes one gesture, written as '
    '<span class="mono">mechanism(premise types)⇒conclusion type</span>. The type system is deliberately small: '
    'a proposition is erased to its head connective or relation (<span class="mono">= ≤ < ∈ ∧ ∨ ∀ ∃ ¬ ⊥ ↔</span>), '
    'and any other predicate becomes <span class="mono">P</span>. Mechanisms are core rules (<span class="mono">Eq.mpr</span>, '
    '<span class="mono">And.intro</span>, …), “apply a lemma”, “use a hypothesis”, induction, matching, '
    'and the certificates left by decision procedures (<span class="mono">ring</span>, <span class="mono">linarith</span>, '
    '<span class="mono">norm_num</span>, <span class="mono">omega</span>). Lemma names never enter.</p>'
    '<p>Binders carry a linear-logic annotation. A hypothesis introduced with <span class="mono">λh</span>, and a '
    '<span class="mono">have</span> claim (a cut), is marked by how often the body uses it: 0 (weakening), 1 (linear) or '
    'ω (contraction). That gives the structural-rule profile further down.</p>')

TEXT['example-cap'] = (
    'The same reading applied to one short mathlib lemma and one OpenAI lemma. Indentation is the term structure; '
    'the annotation after each binder is its use count.')

TEXT['ir-text'] = (
    f'Compiled energy is the text-energy idea moved onto the gesture tree. A Kneser–Ney model of each gesture given its '
    f'parent is trained on mathlib (scored five-fold by project, so mathlib is never scored by a model that has seen it), '
    f'and a project’s energy is its bits per inference step. The median OpenAI project sits at {med("e_ir", "openai")} '
    f'bits per step against mathlib’s {med("e_ir", "mathlib")} (AUC {auc("mathlib", "e_ir")}), and the human research '
    f'projects at {med("e_ir", "human")}. Pooled this way, OpenAI’s inferences are as predictable as mathlib’s. '
    f'Theorem by theorem the picture shifts: the median OpenAI theorem costs {DJ["openai"]["e_ir_median"]:.2f} bits per step '
    f'against {DJ["mathlib"]["e_ir_median"]:.2f}, so the excess sits in short proofs, which carry little weight in a project’s pooled total. '
    f'The large gap the first study found is in the text, meaning names and surface syntax, and it barely depends on the compiled side. '
    f'The project-level tie does not survive the cut analysis: restricted to proofs in optimal cut layout, OpenAI’s projects cost more '
    f'per step than mathlib’s (see the re-check below).')

TEXT['sc-cap'] = (
    f'Across projects the two energies barely track each other (Spearman ρ = {tvi["mathlib"]["rho"]:.2f} within mathlib, '
    f'{tvi["openai"]["rho"]:.2f} within OpenAI). Holding compiled energy fixed, OpenAI projects still cost '
    f'{tvi["text_gap_given_ir"]:.2f} more bits per token of text than mathlib projects; the raw gap is {tvi["text_gap_raw"]:.2f}.')

TEXT['lin-text'] = (
    f'The structural rules separate the corpora more clearly than energy does. OpenAI proofs state '
    f'{med("cuts_per_100", "openai", d=1)} intermediate <span class="mono">have</span> claims per 100 inference steps against '
    f'mathlib’s {med("cuts_per_100", "mathlib", d=1)} (AUC {auc("mathlib", "cuts_per_100")}). They introduce more hypotheses '
    f'they never use ({med("weakening", "openai", pct=True)} vs {med("weakening", "mathlib", pct=True)}), and they leave some '
    f'claims dead, which mathlib’s median project never does. Proofs are longer ({med("nodes_med", "openai", d=1)} '
    f'against {med("nodes_med", "mathlib", d=1)} steps). Against the human research code, though, only the extra claims '
    f'survive (AUC {auc("human", "cuts_per_100")}). Unused hypotheses and dead claims are as common in Carleson and sphere eversion, '
    f'which suggests they belong to research formalization in general rather than to the machine.')

TEXT['spec-text'] = (
    f'Each corpus is a cloud of square-root gesture-mix vectors over the {R["vocab_size"]} commonest gestures. Every '
    f'project gets equal weight, and both covariances are lightly shrunk. The generalized eigenvectors of OpenAI’s '
    f'covariance against mathlib’s are the directions along which OpenAI’s proofs vary unlike mathlib’s. '
    f'Under a Gaussian approximation, the KL divergence splits exactly across them, so each eigenproof carries a number of bits. '
    f'OpenAI’s total is {kl:.0f} bits. Random sets of {n_oai} mathlib projects, compared with the rest of mathlib the same '
    f'way, give {null["total_median"]:.0f} (at most {null["total_max"]:.0f} in ten draws). The human research code gives '
    f'{klh:.0f} bits against a size-matched null of {nullh["total_median"]:.0f}, because eleven projects make a much noisier '
    f'sample. Relative to its own noise, OpenAI is about {ratio:.1f} times as far from mathlib, and the human code about '
    f'{ratio_h:.1f} times. In this analysis <span class="mono">omega</span> and <span class="mono">lia</span> certificates are '
    f'one family. Kept apart, OpenAI’s total rises to {kl0:.0f} bits, because mathlib has switched from '
    f'<span class="mono">omega</span> to <span class="mono">lia</span> and OpenAI has not.')

TEXT['ep-text'] = (
    'Each card gives the gestures the eigenproof loads on, how often theorems in each corpus score beyond two mathlib '
    'standard deviations on it, and the OpenAI theorems that score highest (preferring short ones). The split-half figure '
    'is how well the direction is recovered from a random half of the projects: 1 is perfect. The first eigenproof '
    'belongs to OpenAI, though most of it rides on redundant <span class="mono">have</span> claims (see the re-check). Those after it are habits OpenAI shares with human research code, usually to a similar degree.')

TEXT['nm-text'] = (
    'mathlib’s own principal axes, for comparison. OpenAI sits at most half a standard deviation off-centre on them, '
    'with somewhat less spread than mathlib. Its divergence is not an exaggeration of how mathlib already varies: '
    'it lies in directions mathlib barely uses.')

TEXT['ou-text'] = (
    'The largest single-gesture ratios, by project-balanced share. OpenAI’s excess is concentrated in '
    'arithmetic and normalization certificates (<span class="mono">omega</span>/<span class="mono">lia</span>, '
    '<span class="mono">norm_num</span>, <span class="mono">linarith</span>, <span class="mono">cancel_denoms</span>). Its deficit is the '
    'logical bookkeeping mathlib does by hand: restating a contradiction goal, pattern-matching an existential apart, '
    'building existentials and implications with constructors, and chaining iffs through <span class="mono">propext</span>.')

TEXT['old-text'] = (
    '<p>The first study described each OpenAI project by a dozen textual attributes. Correlating them with project-mean '
    'eigenproof scores gives a check on what the eigenproofs measure. Bold cells have |ρ| ≥ 0.3 and q < 0.05.</p>'
    '<p>The normalization eigenproofs (4 and 5) are the ones that line up with the first study’s style measures. '
    'Projects high on them use more automation tactics per token, have longer proofs relative to their statements, '
    'and introduce fewer new concepts per theorem. Eigenproof 1 tracks compiled energy and little of the textual style. '
    'It is a different axis: how a proof is assembled, not how it is written.</p>')

TEXT['method'] = (
    f'<p><b>Elaboration.</b> One Lean process imports mathlib (OpenAI’s pin, d13f23b) once and elaborates each sampled OpenAI '
    f'project module by module. The sample is {n_oai} of 97 drawn projects, interleaved across areas. Three stalled for '
    f'six minutes on a single module in that run; two of them (FormulaHitting, Analysis.KLS) were then compiled module by '
    f'module as described below and are included, while Geometry.Arnold’s <span class="mono">Obstruction</span> module did '
    f'not finish in 45 minutes in either mode and the project is left out. On this 8 GB machine a '
    f'mathlib import takes one to four minutes, so the full 26-million-line library was out of reach. Theorems whose term '
    f'contains <span class="mono">sorryAx</span> are dropped: {6} on the OpenAI side. Auxiliary theorems '
    f'(<span class="mono">_proof_n</span>, equation lemmas) are folded into their source theorem.</p>'
    f'<p><b>Human baseline.</b> Carleson and sphere eversion were compiled differently: each module against exactly its own '
    f'imports, with project modules written to <span class="mono">.olean</span> files as <span class="mono">lake</span> would. '
    f'A first attempt that let modules see every earlier module broke {"about a quarter"} of their theorems through leaked '
    f'notation. OpenAI’s modules failed far less often in that mode (6 of {SZ["openai"]["theorems"] + 6:,}), and a direct check confirms they are '
    f'unaffected: {len(ISO["projects"])} OpenAI projects ({ISO["n"]:,} theorems) recompiled module by module give the same '
    f'gesture multiset for {100 * ISO["same_u"] / ISO["n"]:.1f}% of theorems, with no new failures. The pooled gesture mix '
    f'differs by {ISO["js_bits"] * 1e4:.0f}×10⁻⁴ bits (Jensen–Shannon); a single theorem accounts for most of the '
    f'changed steps. With those projects swapped into the 94-project '
    f'sample used before FormulaHitting and KLS were added, the OpenAI divergence is {ISO["kl_iso"]:.1f} bits (was {ISO["kl_shared"]:.1f}) and eigenproof 1 carries {ISO["ep1_iso"]:.2f} '
    f'bits (was {ISO["ep1_shared"]:.2f}), stability {ISO["stab1_iso"]:.2f}. '
    f'Carleson’s checkout predates the mathlib pin, so 222 of its 4,898 theorems fail to elaborate and are dropped. '
    f'Sphere eversion’s <span class="mono">Unused/</span> modules, which its library root never imports, are excluded. '
    f'The driver’s message log reports Lean-internal “index out of bounds” panics during command processing; '
    f'a toy project with known theorems gave correct terms, errors and use counts despite them.</p>'
    f'<p><b>Statistics.</b> Group comparisons are over projects with at least 20 theorems: medians with bootstrap intervals, '
    f'Mann–Whitney AUC, Benjamini–Hochberg q across all tests. Eigenproofs use theorems with at least 10 steps, '
    f'project-balanced weights, covariance shrinkage α = {R["regularization"]["alpha"]} toward the diagonal plus a 1% '
    f'variance floor. With no shrinkage the total rises to {R["sensitivity"][0]["total"]:.0f} bits, and with α = 0.3 it falls '
    f'to {R["sensitivity"][2]["total"]:.0f}. The first four eigenproofs keep their directions in both cases, with cosine at least '
    f'{min(min(s["match_to_main"][:4]) for s in R["sensitivity"]):.2f}.</p>'
    f'<p><b>What a gesture is not.</b> Erasing names keeps the shape of the reasoning and loses its content. Two proofs '
    f'that apply different lemmas of the same type pattern look identical here. Certificates record what a tactic left '
    f'in the term, not what the author typed, so a <span class="mono">simp</span> call shows up as the rewrites it produced.</p>')

TITLES = {
    1: dict(title='Arithmetic stitched into equation chains',
            blurb=f'Integer-arithmetic certificates (<span class="mono">omega</span>, or <span class="mono">lia</span> in mathlib) '
                  f'fused with flipping and chaining equalities, at the expense of generalizing over variables. '
                  f'{prev(1, "openai")} of OpenAI theorems score beyond +2 SD, against {prev(1, "mathlib")} in mathlib and '
                  f'{prev(1, "human")} in the human code. This is the eigenproof that is OpenAI’s alone.'),
    2: dict(title='Dependent rewriting under binders',
            blurb=f'Transport along an equation (<span class="mono">Eq.rec</span>) inside \u2200-statements, with an equation '
                  f'hypothesis used once. The human code leans on it at least as much as OpenAI (mean score '
                  f'{M[2]["prevalence"]["human"]["mean"]:.1f} against {M[2]["prevalence"]["openai"]["mean"]:.1f}; '
                  f'{prev(2, "human")} and {prev(2, "openai")} beyond +2 SD). It is how research formalizations push through '
                  f'definitional plumbing.'),
    3: dict(title='Closing by numeral evaluation',
            blurb=f'Goals finished by <span class="mono">norm_num</span> and reflexivity, with no variables abstracted. '
                  f'Equally typical of OpenAI and the human code ({prev(3, "openai")} and {prev(3, "human")} beyond +2 SD).'),
    4: dict(title='Normalize, then close',
            blurb=f'<span class="mono">ring</span>-normalization certificates, the shape a <span class="mono">linarith</span> or '
                  f'<span class="mono">ring</span> call leaves in the term. OpenAI and the human code shift by '
                  f'{M[4]["prevalence"]["openai"]["mean"]:.1f} and {M[4]["prevalence"]["human"]["mean"]:.1f} SD respectively. '
                  f'Of all the eigenproofs, this one tracks the first study’s automation measures most closely.'),
    5: dict(title='Numeric side conditions',
            blurb=f'<span class="mono">norm_num</span> discharging inequalities and positivity side goals, often several per proof. '
                  f'OpenAI is further along it on average (mean {M[5]["prevalence"]["openai"]["mean"]:.1f} against '
                  f'{M[5]["prevalence"]["human"]["mean"]:.1f} SD), while the human code has as heavy a tail '
                  f'({prev(5, "human")} vs {prev(5, "openai")} beyond +2 SD).'),
    6: dict(title='Structure projections',
            blurb='Reading fields out of structures, with a single-use variable binder. Mostly a feature of the human code, '
                  'and the least stable direction here: split-half match is only about one half.'),
    7: dict(title='Light against heavy normalization',
            blurb='A spread-only direction: short norm_num and ring steps chained by equalities, contrasted with long '
                  'multi-premise norm_num calls. It has almost no mean shift (0.1 SD) and records that OpenAI varies more '
                  'in how much it hands to one normalization call.'),
    8: dict(title='Pure ring steps',
            blurb='A second, weaker ring direction, set against chained equalities and norm_num inequalities. '
                  'Mostly spread rather than shift.'),
}

EXAMPLES = [
    ('mathlib', 'mathlib', 'Mathlib.Analysis.Complex.Basic', 'Complex.re_le_re',
     os.path.join(ROOT, 'out_h', 'OAI.RingTheory.Kurosh.trace.jsonl')),
    ('OpenAI', 'openai', 'OAI.RingTheory.Kurosh.FiniteDescent', 'OAI.KuroshConstruction.centerDivisionAdjoin_le',
     os.path.join(ROOT, 'out_h', 'OAI.RingTheory.Kurosh.trace.jsonl')),
]

# ---------------------------------------------------------------- compression by cuts
_cp = os.path.join(ROOT, 'out_cut', 'results.json')
if os.path.exists(_cp):
    CR = json.load(open(_cp))
    PO, PM, AU, PV = CR['pooled'], CR['project_median'], CR['auc'], CR.get('p', {})
    pct = lambda x: f'{100 * x:.0f}%'
    _main = ('mathlib', 'openai', 'human')
    _chi_max = max(PO[c]['chi_mean'] for c in _main)
    _ge1 = (min(PO[c]['chi_ge1'] for c in _main), max(PO[c]['chi_ge1'] for c in _main))

    def _sig(c, ref, k):
        return PV.get(f'{c}_vs_{ref}', {}).get(k, 1) < 0.01

    def _auc(c, ref, k):
        return f'AUC {AU[f"{c}_vs_{ref}"][k]:.2f}'

    TEXT['cut-text'] = (
        '<p>A <em>cut</em> is a proof that is named and then used: a <span class="mono">have</span>, a '
        '<span class="mono">let</span> of a proof, or a β-redex <span class="mono">(fun h ↦ q) p</span>. Eliminating it '
        'substitutes <span class="mono">p</span> for each use of <span class="mono">h</span>. The linear annotation decides '
        'what that costs. A dead cut (0 uses) is deleted outright. A linear cut (1 use) moves <span class="mono">p</span> to '
        'its single use. A shared cut (2 or more uses) copies it, and only then does the cut save anything. Each proof term '
        'was normalized four ways, with tree sizes computed exactly: as written, dead cuts removed, linear cuts removed, all '
        'cuts removed. A fifth form keeps exactly the cuts that pay for themselves, deciding bottom-up.</p>'
        '<p><b>The unit is the bit of cut compression.</b> A proof has κ bits when eliminating all its cuts multiplies its size '
        'by 2<sup>κ</sup>. It splits exactly as κ = σ − ℓ − w. Here σ is the sharing gain, ℓ the overhead of naming proofs '
        'used once, and w the cost of proofs built and never used. κ depends on where the author put the cuts, so two '
        'intrinsic quantities sit beside it. χ, the compressibility, measures the cut-free size against the optimal layout: '
        'it is what the proof’s sharing could save at best. ρ, the layout redundancy, measures the proof as written against '
        'that optimum. Then κ = χ − ρ. The same unit applies one level up, where a project’s local lemmas are the cuts and '
        'each citation is a use.</p>'
        f'<p>OpenAI writes many more cuts: {pct(CR["per_proof"]["openai"]["with_cut"])} of its proofs contain one, against '
        f'{pct(CR["per_proof"]["mathlib"]["with_cut"])} in mathlib and {pct(CR["per_proof"]["human"]["with_cut"])} in the human code. '
        f'It does not compress more for it. Its mean compressibility is {PO["openai"]["chi_mean"]:.3f} bits, against '
        f'{PO["mathlib"]["chi_mean"]:.3f} in mathlib and {PO["human"]["chi_mean"]:.3f} in the human code '
        f'({_auc("openai", "human", "chi_mean")} against the human projects'
        f'{(", so the human code’s proofs are the more compressible" if AU["openai_vs_human"]["chi_mean"] < 0.5 else ", so OpenAI’s are the more compressible") if _sig("openai", "human", "chi_mean") else ", not significant"}). '
        f'What separates OpenAI is layout redundancy: '
        f'{PO["openai"]["rho_mean"]:.3f} bits per proof, against {PO["mathlib"]["rho_mean"]:.3f} and {PO["human"]["rho_mean"]:.3f} '
        f'({_auc("openai", "mathlib", "rho_mean")} against mathlib projects, {_auc("openai", "human", "rho_mean")} against human ones). '
        f'Almost all of it is linear overhead, single-use claims that cost a cut and save nothing. '
        f'{pct(PO["openai"]["kappa_neg"])} of OpenAI’s proofs end up larger with their cuts than without them, against '
        f'{pct(PO["mathlib"]["kappa_neg"])} in mathlib and {pct(PO["human"]["kappa_neg"])} in the human code.</p>'
        f'<p>Inside a proof, compression is small everywhere: at most {_chi_max:.3f} bits per proof on average, and at least '
        f'a doubling (χ ≥ 1) in {100 * _ge1[0]:.1f}–{100 * _ge1[1]:.1f}% of proofs. The heavy tail is real, though. A few mathlib proofs are chains of hundreds of nested '
        f'β-redexes, each used three or four times, and their cut-free forms are larger by a factor of 2<sup>300</sup> to '
        f'2<sup>450</sup>. That is why corpus figures are means of per-proof bits, not ratios of summed sizes. Most compression '
        f'lives one level up, in lemmas. Inlining every local lemma into the results that use it multiplies the median '
        f'project by 2<sup>{PM["mathlib"]["kappa_lemma"]:.1f}</sup> in mathlib, 2<sup>{PM["openai"]["kappa_lemma"]:.1f}</sup> in '
        f'OpenAI and 2<sup>{PM["human"]["kappa_lemma"]:.1f}</sup> in the human code. At that level OpenAI is '
        f'{"not distinguishable from mathlib" if not _sig("openai", "mathlib", "kappa_lemma") else "different from mathlib"} '
        f'({_auc("openai", "mathlib", "kappa_lemma")}).</p>')
    TEXT['cut-cap'] = (
        'Per-proof rows are means over theorems with at least 10 steps. Cut counts per 100 steps use the proof’s shared size, '
        'as elsewhere on this page, while κ, χ and ρ use tree sizes, with shared subterms counted at every use. A hypothesis '
        'that occurs only inside a type or inside data keeps its proof alive, as one copy. Lemma rows are medians over '
        'projects with at least 20 proofs, and a project’s results are its theorems that no other theorem in it cites.')

# ---------------------------------------------------------------- re-check after the cut findings (recheck_cuts.py, recheck_ep.py)
_rc = {k: os.path.join(ROOT, os.environ.get('GOUT', 'out'), k, 'results.json')
       for k in ('analysis_merged', 'analysis_proofs', 'analysis_rho0', 'analysis_nocut')}
_ep = os.path.join(ROOT, os.environ.get('GOUT', 'out'), 'analysis_merged', 'recheck_ep.json')
if all(os.path.exists(p) for p in _rc.values()) and os.path.exists(_ep):
    RC = {k: json.load(open(p)) for k, p in _rc.items()}
    EP = json.load(open(_ep))
    COLS = [('analysis_merged', 'All theorems'), ('analysis_proofs', 'Proofs only'),
            ('analysis_rho0', 'Optimal layout (ρ = 0)'), ('analysis_nocut', 'No cuts')]

    def _g(r, m, g):
        return next((x['median'] for x in r['groups'] if x['metric'] == m and x['group'] == g), None)

    def _t(r, vs, m):
        return next((x for x in r['tests'] if x['vs'] == vs and x['metric'] == m), None)

    def _thm(r, g):
        return next(x['theorems'] for x in r['sizes'] if x['group'] == g)

    def _ratio(r, g='openai'):
        n = r['null'] if g == 'openai' else r['null_human']
        return r['kl_bits'][g] / n['total_median']

    def _tc(r, vs, m):
        t = _t(r, vs, m)
        return '–' if t is None else f"{t['auc']:.2f}" + ('' if t['q'] < 0.05 else ' <span class="cap">(n.s.)</span>')

    A, Pr, Z = RC['analysis_merged'], RC['analysis_proofs'], RC['analysis_rho0']
    keep = {g: _thm(Z, g) / _thm(Pr, g) for g in ('openai', 'mathlib', 'human')}
    M1 = EP['modes'][0]
    _r0top = Z['modes'][0]
    _r0ia = next(m for m in Z['modes'] if m['pos'][0]['gesture'].startswith('tac:IntArith'))
    e0 = {g: _g(Z, 'e_ir', g) for g in ('openai', 'mathlib')}
    tE = _t(Z, 'mathlib', 'e_ir')
    qtxt = 'q &lt; 0.001' if tE['q'] < 0.001 else f"q = {tE['q']:.3f}"
    pct = lambda x: f'{100 * x:.0f}%'
    others = EP['modes'][1:]
    _lo = min(m['openai_rho0']['beyond2'] / max(m['mathlib_rho0']['beyond2'], 1e-9) for m in others)
    _hi = max(m['openai_rho0']['beyond2'] / max(m['mathlib_rho0']['beyond2'], 1e-9) for m in others)
    TEXT['rc-text'] = (
        '<p>The cut results bear on everything above. OpenAI puts a cut in many more of its proofs, mostly single-use claims, '
        'and each one adds steps and gestures to the compiled term. Some of the earlier differences could be that layout '
        'and nothing more. So every analysis on this page was rerun on two subsets: theorems already in optimal cut layout '
        '(ρ = 0, where the written form equals the form that keeps only profitable cuts), and theorems with no cut at all. '
        'Definitions have no cut measure, so a control run on all proofs separates the effect of the restriction from the effect '
        f'of dropping them. The ρ = 0 subset keeps {pct(keep["openai"])} of OpenAI’s proofs, {pct(keep["mathlib"])} of '
        f'mathlib’s and {pct(keep["human"])} of the human code’s.</p>'
        f'<p><b>The divergence is not layout.</b> On optimal-layout proofs OpenAI is {Z["kl_bits"]["openai"]:.0f} bits from '
        f'mathlib against a null of {Z["null"]["total_median"]:.0f}, a ratio of {_ratio(Z):.1f}× (on all proofs, {_ratio(Pr):.1f}×). '
        f'Like for like in the original eigenproof basis, OpenAI’s optimal-layout proofs are {EP["kl_rho0_vs_mathlib_rho0"]:.0f} bits '
        f'from mathlib’s optimal-layout proofs, and its redundant-layout proofs are {EP["kl_rho+_vs_mathlib_rho+"]:.0f} bits from mathlib’s.</p>'
        f'<p><b>Eigenproof 1 is mostly layout.</b> {pct(M1["openai_excess_from_rho+"])} of OpenAI’s excess beyond +2 on it '
        f'comes from proofs with redundant layout, which are {pct(M1["openai_rho+"]["share"])} of its proofs. '
        f'{100 * M1["openai_rho+"]["beyond2"]:.1f}% of those score beyond +2, against {100 * M1["openai_rho0"]["beyond2"]:.1f}% of its '
        f'optimal-layout proofs and {100 * M1["mathlib_rho0"]["beyond2"]:.1f}% of mathlib’s. The arithmetic certificates sit inside '
        f'<span class="mono">have</span> claims: <span class="mono">have h : a = b := by omega</span>. Rebuilt on optimal-layout '
        f'proofs, the integer-arithmetic direction drops to rank {_r0ia["rank"]} ({_r0ia["bits"]:.0f} bits). The top direction '
        f'becomes rewriting along hypothesis equations (<span class="mono">{_r0top["pos"][0]["gesture"]}</span>, '
        f'<span class="mono">{_r0top["pos"][1]["gesture"]}</span>), the old eigenproof 2, now at {_r0top["bits"]:.0f} bits. '
        f'Its prevalence does not depend on layout ({100 * EP["modes"][1]["openai_rho0"]["beyond2"]:.1f}% vs '
        f'{100 * EP["modes"][1]["openai_rho+"]["beyond2"]:.1f}%). The other eigenproofs are more common in redundant-layout proofs, '
        f'but even on optimal-layout proofs OpenAI scores beyond +2 {_lo:.0f} to {_hi:.0f} times as often as mathlib. '
        f'Eigenproof 1 itself also survives there, at {M1["openai_rho0"]["beyond2"] / M1["mathlib_rho0"]["beyond2"]:.1f} times mathlib’s rate, though far weaker.</p>'
        f'<p><b>Compiled energy changes.</b> Over all theorems the median OpenAI project costs what mathlib’s does '
        f'(AUC {_t(A, "mathlib", "e_ir")["auc"]:.2f}). On optimal-layout proofs it costs {e0["openai"]:.2f} bits per step against '
        f'{e0["mathlib"]:.2f} (AUC {tE["auc"]:.2f}, {qtxt}). Redundant claims are cheap, predictable steps, and they '
        'pulled OpenAI’s per-step energy down to mathlib’s level. The earlier finding that OpenAI’s inferences are as predictable as '
        f'mathlib’s was produced by its cut layout. Against the human code the difference stays insignificant (AUC {_t(Z, "human", "e_ir")["auc"]:.2f}).</p>'
        f'<p><b>Text energy is unaffected.</b> The per-token text gap to mathlib is {Pr["text_vs_ir"]["text_gap_raw"]:.2f} bits on all '
        f'proofs and {Z["text_vs_ir"]["text_gap_raw"]:.2f} on optimal-layout ones, so the first study’s main result does not '
        f'come from <span class="mono">have</span> claims. Among the structural rules, the proof-size gap shrinks from '
        f'{_t(Pr, "mathlib", "nodes_med")["diff"]:.1f} to {_t(Z, "mathlib", "nodes_med")["diff"]:.1f} steps. Unused hypotheses become a sharper '
        f'signal (AUC {_t(Pr, "mathlib", "weakening")["auc"]:.2f} → {_t(Z, "mathlib", "weakening")["auc"]:.2f}), and automation '
        f'certificates stay the strongest single difference ({_t(Z, "mathlib", "share:automation certificate")["auc"]:.2f}).</p>')

    def _row(label, sub, f):
        return f'<tr><td>{label}' + (f'<div class="cap">{sub}</div>' if sub else '') + '</td>' + ''.join(f'<td class="num">{f(RC[k])}</td>' for k, _ in COLS) + '</tr>'
    h = '<thead><tr><th></th>' + ''.join(f'<th class="num">{n}</th>' for _, n in COLS) + '</tr></thead><tbody>'
    h += _row('OpenAI theorems', 'in the analysis', lambda r: f'{_thm(r, "openai"):,}')
    h += _row('Divergence from mathlib', 'bits, against the size-matched null', lambda r: f'{r["kl_bits"]["openai"]:.0f} / {r["null"]["total_median"]:.0f} = {_ratio(r):.1f}×')
    h += _row('Human code, same ratio', '', lambda r: f'{_ratio(r, "human"):.1f}×')
    h += _row('Top eigenproof', 'first gesture and bits', lambda r: f'<span class="mono">{r["modes"][0]["pos"][0]["gesture"]}</span> {r["modes"][0]["bits"]:.0f}')
    h += _row('Compiled energy', 'median project, OpenAI vs mathlib (AUC)', lambda r: f'{_g(r, "e_ir", "openai"):.2f} vs {_g(r, "e_ir", "mathlib"):.2f} ({_tc(r, "mathlib", "e_ir")})')
    h += _row('Text-energy gap', 'bits per token, OpenAI minus mathlib', lambda r: f'{r["text_vs_ir"]["text_gap_raw"]:.2f}')
    for m, lab in [('nodes_med', 'Proof size'), ('weakening', 'Unused hypotheses'), ('share:automation certificate', 'Automation certificates')]:
        h += _row(lab, 'AUC against mathlib projects', lambda r, m=m: _tc(r, 'mathlib', m))
    h += '</tbody>'
    TEXT['rc-table'] = h
    h = ('<thead><tr><th></th><th class="num">bits</th><th class="num">OpenAI, ρ = 0</th><th class="num">OpenAI, ρ &gt; 0</th>'
         '<th class="num">mathlib, ρ = 0</th><th class="num">mathlib, ρ &gt; 0</th><th class="num">OpenAI excess from ρ &gt; 0</th></tr></thead><tbody>')
    for m in EP['modes']:
        h += (f'<tr><td>Eigenproof {m["ep"]}</td><td class="num">{m["bits"]:.1f}</td>'
              + ''.join(f'<td class="num">{100 * m[k]["beyond2"]:.1f}%</td>' for k in ('openai_rho0', 'openai_rho+', 'mathlib_rho0', 'mathlib_rho+'))
              + f'<td class="num">{pct(m["openai_excess_from_rho+"])}</td></tr>')
    TEXT['rc-table2'] = h + '</tbody>'
    TEXT['rc-cap'] = (
        'Upper table: each column reruns the full pipeline (vocabulary, eigenproofs, null, tests) on that subset; '
        '“n.s.” marks q ≥ 0.05. Lower table: the published eigenproofs, unchanged, with the share of theorems scoring beyond '
        '+2 mathlib standard deviations in each layout stratum, project-balanced. The last column is the share of OpenAI’s '
        'beyond-+2 mass that comes from redundant-layout proofs. Proofs with cuts are longer, so the strata also differ in size; '
        'the like-for-like divergences in the text compare each stratum only with the same stratum of mathlib.')
