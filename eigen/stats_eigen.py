"""Project-level compiled statistics and eigenproofs.

Reads out/analysis/decls.pkl and unigrams.pkl (from analyze.py). Writes out/analysis/results.json.
"""
import collections
import json
import math
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd
from scipy import linalg, stats

sys.path.insert(0, '/Users/safsom/Projects/math-ai-projects/energy')
from lexer import declarations, strip_comments  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.environ.get('GOUT', os.path.join(HERE, 'out')), os.environ.get('RESNAME', 'analysis'))
MIN_THM = 20
K = 300
MIN_NODES = 10
B = 4000
rng = np.random.default_rng(20261010)

D = pd.read_pickle(os.path.join(RES, 'decls.pkl'))
blob = pickle.load(open(os.path.join(RES, 'unigrams.pkl'), 'rb'))
U = blob['U']

# ------------------------------------------------------------------ project table
fam_cols = [c for c in D.columns if c.startswith('fam:')]
agg = {'name': 'size', 'E_ir': 'sum', 'steps': 'sum', 'nodes': ['sum', 'median'],
       **{f'hyp_{m}': 'sum' for m in '01ω'}, **{f'cut_{m}': 'sum' for m in '01ω'}, **{c: 'sum' for c in fam_cols}}
P = D.groupby(['group', 'project']).agg(agg)
P.columns = ['n', 'E', 'steps', 'nodes', 'nodes_med'] + [f'hyp_{m}' for m in '01ω'] + [f'cut_{m}' for m in '01ω'] + fam_cols
P = P.reset_index()
P['e_ir'] = P.E / P.steps
hyp = P[[f'hyp_{m}' for m in '01ω']].sum(1)
cut = P[[f'cut_{m}' for m in '01ω']].sum(1)
P['weakening'] = P.hyp_0 / hyp
P['linear'] = P.hyp_1 / hyp
P['contraction'] = P['hyp_ω'] / hyp
P['cuts_per_100'] = 100 * cut / P.nodes
P['dead_cut'] = P.cut_0 / cut.replace(0, np.nan)
P['single_use_cut'] = P.cut_1 / cut.replace(0, np.nan)
for c in fam_cols:
    P['share:' + c[4:]] = P[c] / P.nodes
P = P[P.n >= MIN_THM].copy()

text = pd.read_csv('/Users/safsom/Projects/math-ai-projects/energy/data/out/projects.csv')[['project', 'e_tok', 'e_prem']]
P = P.merge(text, on='project', how='left')
P.to_csv(os.path.join(RES, 'projects.csv'), index=False)

METRICS = {
    'e_ir': ('Compiled energy', 'bits per inference step under mathlib\'s gesture grammar (names erased)'),
    'nodes_med': ('Proof size', 'median inference steps per theorem'),
    'weakening': ('Unused hypotheses', 'share of introduced hypotheses never used (weakening)'),
    'linear': ('Linear hypotheses', 'share of introduced hypotheses used exactly once'),
    'contraction': ('Reused hypotheses', 'share of introduced hypotheses used more than once (contraction)'),
    'cuts_per_100': ('Intermediate claims', 'have/let cuts per 100 inference steps'),
    'single_use_cut': ('Single-use claims', 'share of have-cuts used exactly once'),
    'dead_cut': ('Unused claims', 'share of have-cuts never used'),
}
FAMS = [c[4:] for c in fam_cols]
for f in FAMS:
    METRICS['share:' + f] = (f[0].upper() + f[1:], f'share of inference steps that {f}')

GROUPS = ['mathlib', 'openai', 'human', 'human-upstream']


def boot_median(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return (float(np.median(x)) if len(x) else None, None, None)
    bs = np.median(rng.choice(x, (B, len(x))), axis=1)
    return float(np.median(x)), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))


group_rows = []
for m, (lab, dfn) in METRICS.items():
    for g in GROUPS:
        med, lo, hi = boot_median(P.loc[P.group == g, m])
        group_rows.append(dict(metric=m, label=lab, definition=dfn, group=g, n=int((P.group == g).sum()),
                               median=med, lo=lo, hi=hi))


def bh(p):
    p = np.asarray(p)
    o = np.argsort(p)
    q = p[o] * len(p) / (np.arange(len(p)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty_like(q)
    out[o] = np.minimum(q, 1)
    return out


tests = []
for ref in ['mathlib', 'human']:
    for m in METRICS:
        a = P.loc[P.group == 'openai', m].dropna().to_numpy()
        b = P.loc[P.group == ref, m].dropna().to_numpy()
        if len(a) < 3 or len(b) < 3:
            continue
        u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
        d = np.median(rng.choice(a, (B, len(a))), 1) - np.median(rng.choice(b, (B, len(b))), 1)
        tests.append(dict(vs=ref, metric=m, label=METRICS[m][0], diff=float(np.median(a) - np.median(b)),
                          lo=float(np.quantile(d, .025)), hi=float(np.quantile(d, .975)), auc=float(u / (len(a) * len(b))),
                          p=float(p), n_openai=len(a), n_ref=len(b)))
T = pd.DataFrame(tests, columns=['vs', 'metric', 'label', 'diff', 'lo', 'hi', 'auc', 'p', 'n_openai', 'n_ref'])
T['q'] = bh(T.p) if len(T) else []

# text vs compiled energy across projects
tvc = {}
for g in ['mathlib', 'openai']:
    s = P[P.group == g].dropna(subset=['e_tok'])
    r = stats.spearmanr(s.e_tok, s.e_ir)
    tvc[g] = dict(rho=float(r.statistic), p=float(r.pvalue), n=len(s))
both = P[P.group.isin(['mathlib', 'openai'])].dropna(subset=['e_tok']).copy()
both['oai'] = (both.group == 'openai').astype(float)
Xr = np.column_stack([np.ones(len(both)), both.oai, both.e_ir])
beta, *_ = np.linalg.lstsq(Xr, both.e_tok.to_numpy(), rcond=None)
tvc['text_gap_raw'] = float(both[both.oai == 1].e_tok.median() - both[both.oai == 0].e_tok.median())
tvc['text_gap_given_ir'] = float(beta[1])

# ------------------------------------------------------------------ eigenproofs
idx = np.flatnonzero((D.nodes >= MIN_NODES).to_numpy() & D.group.isin(['mathlib', 'openai', 'human']).to_numpy())
grp = D.group.to_numpy()
proj = D.project.to_numpy()


def balanced_weights(ix):
    """Each project gets equal total weight inside its group."""
    w = np.zeros(len(ix))
    for g in set(grp[ix]):
        m = grp[ix] == g
        counts = collections.Counter(proj[ix][m])
        w[m] = [1.0 / counts[p] for p in proj[ix][m]]
        w[m] /= w[m].sum()
    return w


share = collections.defaultdict(lambda: collections.Counter())
W0 = balanced_weights(idx)
for j, i in enumerate(idx):
    tot = sum(U[i].values())
    for g, c in U[i].items():
        share[grp[i]][g] += W0[j] * c / tot
score = collections.Counter()
for g in set(share['mathlib']) | set(share['openai']):
    score[g] = share['mathlib'][g] + share['openai'][g]
vocab = [g for g, _ in score.most_common(K)]
vix = {g: k for k, g in enumerate(vocab)}
X = np.zeros((len(idx), K + 1))
for j, i in enumerate(idx):
    tot = sum(U[i].values())
    for g, c in U[i].items():
        X[j, vix.get(g, K)] += c / tot
X = np.sqrt(X)


def wmoments(Xs, w):
    mu = w @ Xs
    Z = Xs - mu
    return mu, (Z * w[:, None]).T @ Z


gi = grp[idx]
mats = {}
for g in ['mathlib', 'openai', 'human']:
    m = gi == g
    w = W0[m] / W0[m].sum()
    mats[g] = wmoments(X[m], w)
muM, SM = mats['mathlib']
ALPHA, FLOOR = 0.1, 0.01


def regularize(S, alpha=ALPHA, floor=FLOOR):
    """Shrink toward the diagonal and add a variance floor (a fraction of the mean variance)."""
    d = np.diag(S)
    return (1 - alpha) * S + alpha * np.diag(d) + floor * max(d.mean(), 1e-4) * np.eye(len(d))


SMr = regularize(SM)
eps = FLOOR * np.diag(SM).mean()


def gen_eig(mu_o, S_o, mu_m=muM, S_m=SM, alpha=ALPHA, floor=FLOOR):
    """Generalized eigenproofs of group o against reference m (both covariances regularized alike)."""
    lam, Wv = linalg.eigh(regularize(S_o, alpha, floor), regularize(S_m, alpha, floor))
    delta = Wv.T @ (mu_o - mu_m)
    contrib = 0.5 * (lam - 1 - np.log(lam) + delta ** 2) / math.log(2)  # bits
    order = np.argsort(-contrib)
    return lam[order], Wv[:, order], delta[order], contrib[order]


lam, Wv, delta, contrib = gen_eig(*mats['openai'])
lamH, WH, deltaH, contribH = gen_eig(*mats['human'])
names_all = vocab + ['(other gestures)']

from gloss import describe  # noqa: E402


# source text for exemplars
SRC_ROOTS = {'mathlib': '/Users/safsom/Projects/math-ai-projects/mathlib4',
             'openai': '/Users/safsom/Projects/math-ai-projects/corpora/openai_math/lean'}
_src_cache = {}


def source_of(corpus, module, name):
    if corpus == 'human':
        root = os.path.join(HERE, 'human', 'carleson' if module.startswith('Carleson') else 'SphereEversion')
    else:
        root = SRC_ROOTS[corpus]
    path = os.path.join(root, *module.split('.')) + '.lean'
    if path not in _src_cache:
        try:
            _src_cache[path] = list(declarations(strip_comments(open(path, encoding='utf-8').read())))
        except OSError:
            _src_cache[path] = []
    short = name.split('.')[-1]
    best = None
    for d in _src_cache[path]:
        full = '.'.join(d['namespace'] + [d['name']]) if d['name'] else ''
        if full == name or full.endswith('.' + name) or name.endswith('.' + full):
            return d['text']
        if d['name'].split('.')[-1] == short and best is None:
            best = d['text']
    return best


THM_HEAD = re.compile(r'^\s*(@\[[^\]]*\]\s*)*((private|protected|nonrec)\s+)*(theorem|lemma)\b')


def exemplars(sc, which, k=3, maxlen=900, prefer_short=True):
    m = (gi == which)
    cand = np.flatnonzero(m)
    nodes = D.nodes.to_numpy()[idx][cand]
    # among the top 2% by score, prefer readable (shorter) proofs
    top = cand[np.argsort(-sc[cand])[:max(20, int(0.02 * len(cand)))]]
    if prefer_short:
        top = sorted(top, key=lambda j: (D.nodes.iat[idx[j]] > 120, -sc[j]))
    out, seen_proj = [], set()
    for j in top:
        i = idx[j]
        p = D.project.iat[i]
        if p in seen_proj:
            continue
        txt = source_of(D.corpus.iat[i], D.module.iat[i], D.name.iat[i])
        if not txt or len(txt) > maxlen or not THM_HEAD.match(txt):
            continue
        seen_proj.add(p)
        out.append(dict(name=D.name.iat[i], project=p, score=float(sc[j]), nodes=int(D.nodes.iat[i]), text=txt))
        if len(out) == k:
            break
    return out


def mode_record(w, lam_k, delta_k, contrib_k, rank, base_mu=muM):
    if delta_k < 0:
        w, delta_k = -w, -delta_k
    pattern = SMr @ w
    pattern = pattern / np.linalg.norm(pattern)
    sc = (X - base_mu) @ w
    order = np.argsort(-pattern)
    pos = [dict(gesture=names_all[k], desc=describe(names_all[k]), loading=float(pattern[k])) for k in order[:8]]
    neg = [dict(gesture=names_all[k], desc=describe(names_all[k]), loading=float(pattern[k])) for k in order[::-1][:6]]
    prev = {}
    for g in ['mathlib', 'openai', 'human']:
        m = gi == g
        ww = W0[m] / W0[m].sum()
        prev[g] = dict(mean=float(ww @ sc[m]), sd=float(np.sqrt(ww @ (sc[m] - ww @ sc[m]) ** 2)),
                       beyond2=float(ww @ (sc[m] > 2)))
    return dict(rank=rank, lam=float(lam_k), shift=float(delta_k), bits=float(contrib_k), pos=pos, neg=neg,
                prevalence=prev, ex_openai=exemplars(sc, 'openai'), ex_mathlib=exemplars(sc, 'mathlib', k=2),
                ex_human=exemplars(sc, 'human', k=1))


modes = [mode_record(Wv[:, k], lam[k], delta[k], contrib[k], k + 1) for k in range(8)]

# split-half stability of the top eigenproofs (projects split at random)
def subset_eig(proj_keep):
    keep = np.isin(proj[idx], list(proj_keep))
    res = {}
    for g in ['mathlib', 'openai']:
        m = (gi == g) & keep
        w = W0[m] / W0[m].sum()
        res[g] = wmoments(X[m], w)
    S = regularize(res['mathlib'][1])
    l, Wh, d, c = gen_eig(res['openai'][0], res['openai'][1], res['mathlib'][0], res['mathlib'][1])
    pats = (S @ Wh[:, :8])
    return pats / np.linalg.norm(pats, axis=0)


full_pats = np.stack([SMr @ Wv[:, k] / np.linalg.norm(SMr @ Wv[:, k]) for k in range(8)], 1)
stab = []
projects_by_group = {g: sorted(set(proj[idx][gi == g])) for g in ['mathlib', 'openai']}
for rep in range(10):
    half = set()
    for g, ps in projects_by_group.items():
        perm = rng.permutation(len(ps))
        half |= {ps[t] for t in perm[:len(ps) // 2]}
    pats = subset_eig(half)
    cos = np.abs(full_pats.T @ pats)
    stab.append(cos.max(1))
stability = np.mean(stab, 0).tolist()

# mathlib's own normal modes (PCA of the mathlib gesture distribution)
ev, V = linalg.eigh(SM)
ev, V = ev[::-1], V[:, ::-1]
normal = []
SO = mats['openai'][1]
muO = mats['openai'][0]
for k in range(5):
    v = V[:, k]
    sc = (X - muM) @ v / math.sqrt(ev[k])
    if (muO - muM) @ v < 0:
        v, sc = -v, -sc
    order = np.argsort(-v)
    normal.append(dict(rank=k + 1, var_share=float(ev[k] / ev.sum()),
                       pos=[dict(gesture=names_all[j], desc=describe(names_all[j]), loading=float(v[j])) for j in order[:6]],
                       neg=[dict(gesture=names_all[j], desc=describe(names_all[j]), loading=float(v[j])) for j in order[::-1][:5]],
                       openai_shift=float((muO - muM) @ v / math.sqrt(ev[k])),
                       openai_var_ratio=float(v @ SO @ v / ev[k]),
                       excess_bits=float(0.5 * ((v @ SO @ v + ((muO - muM) @ v) ** 2) / ev[k] - 1) / math.log(2)),
                       ex_mathlib=exemplars(sc, 'mathlib', k=2)))

# null: a random set of mathlib projects (same size as the comparison group) against the rest of mathlib
def null_for(n_proj, reps=10):
    mlp = projects_by_group['mathlib']
    out = []
    for rep in range(reps):
        perm = rng.permutation(len(mlp))
        A_ = {mlp[t] for t in perm[:n_proj]}
        inA = np.isin(proj[idx], list(A_))
        mA = (gi == 'mathlib') & inA
        mB = (gi == 'mathlib') & ~inA
        wA = balanced_weights(idx[mA])
        wB = balanced_weights(idx[mB])
        muA, SA = wmoments(X[mA], wA / wA.sum())
        muB, SB = wmoments(X[mB], wB / wB.sum())
        l0, _, d0, c0 = gen_eig(muA, SA, muB, SB)
        out.append(dict(total=float(c0.sum()), top=[float(x) for x in c0[:20]], lam=[float(x) for x in l0[:20]]))
    tops = np.array([n['top'] for n in out])
    return dict(n_projects=n_proj, total_median=float(np.median([n['total'] for n in out])),
                total_max=float(np.max([n['total'] for n in out])),
                top_median=np.median(tops, 0).tolist(), top_max=np.max(tops, 0).tolist(),
                lam_median=np.median(np.array([n['lam'] for n in out]), 0).tolist())


n_oai_proj = len(set(proj[idx][gi == 'openai']))
n_hum_proj = len(set(proj[idx][gi == 'human']))
null_summary = null_for(n_oai_proj)
null_human = null_for(max(3, n_hum_proj))

sens = []
for a_, f_ in [(0.0, 0.001), (0.1, 0.01), (0.3, 0.05)]:
    l_, W_, d_, c_ = gen_eig(*mats['openai'], muM, SM, a_, f_)
    pats = np.stack([regularize(SM, a_, f_) @ W_[:, k] for k in range(8)], 1)
    pats /= np.linalg.norm(pats, axis=0)
    match = np.abs(full_pats.T @ pats).max(1)
    sens.append(dict(alpha=a_, floor=f_, total=float(c_.sum()), top=[float(x) for x in c_[:8]],
                     match_to_main=[float(x) for x in match]))

# per-project eigenproof scores (OpenAI) against the original study's attributes
proj_scores = pd.DataFrame({'project': proj[idx], 'group': gi})
for md, k in zip(modes, range(8)):
    w = Wv[:, k] * (1 if delta[k] >= 0 else -1)
    proj_scores[f'ep{k + 1}'] = (X - muM) @ w
PS = proj_scores.groupby(['group', 'project']).mean().reset_index()
old = pd.read_csv('/Users/safsom/Projects/math-ai-projects/proofstudy/results/project_metrics.csv')
old = old[old.group == 'openai_math'].copy()
old['project'] = 'OAI/' + old.project
OLDK = ['concepts_per_100_thm', 'live_concept_share', 'single_use_lemma_share', 'cert_token_share', 'casebash_token_share',
        'auto_per_1k', 'struct_per_1k', 'numbered_share', 'uninformative_share', 'grounding', 'propagation',
        'skel_dup_share', 'library_ref_share', 'proof_to_statement']
J = PS[PS.group == 'openai'].merge(old[['project'] + OLDK], on='project').merge(P[['project', 'e_ir', 'e_tok']], on='project', how='left')
old_corr = {}
for k in range(8):
    row = {}
    for a in OLDK + ['e_ir', 'e_tok']:
        s_ = J[[f'ep{k + 1}', a]].dropna()
        if len(s_) >= 10:
            r_ = stats.spearmanr(s_.iloc[:, 0], s_.iloc[:, 1])
            row[a] = dict(rho=float(r_.statistic), p=float(r_.pvalue), n=len(s_))
    old_corr[f'ep{k + 1}'] = row

# per-declaration join of text energy and compiled energy
TE = pd.read_pickle('/Users/safsom/Projects/math-ai-projects/energy/data/text_energy.pkl')
TE = TE[TE.kind.isin(['theorem', 'lemma'])][['corpus', 'project', 'full', 'E_struct', 'n_tok', 'E_n', 'n_n', 'E_o', 'n_o']]
TE['project'] = TE.project.str.replace('Carleson', 'Carleson').str.replace('SphereEversion', 'SphereEversion')
TE = TE.drop_duplicates(['corpus', 'full'])
DJ = D[D.group.isin(['mathlib', 'openai'])].merge(TE[TE.corpus.isin(['mathlib', 'openai'])].rename(columns={'full': 'name', 'project': 'tproj'}),
                                                  on=['corpus', 'name'], how='inner')
DJ = DJ[(DJ.steps >= 5) & (DJ.n_tok >= 10)].copy()
DJ['e_ir_d'] = DJ.E_ir / DJ.steps
DJ['e_tok_d'] = DJ.E_struct / DJ.n_tok
DJ['e_name_d'] = DJ.E_n / DJ.n_n.clip(lower=1)
DJ['e_op_d'] = DJ.E_o / DJ.n_o.clip(lower=1)
decl_join = {}
for g in ['mathlib', 'openai']:
    s_ = DJ[DJ.group == g]
    decl_join[g] = dict(n=len(s_), rho_ir_text=float(stats.spearmanr(s_.e_ir_d, s_.e_tok_d).statistic),
                        rho_ir_names=float(stats.spearmanr(s_.e_ir_d, s_.e_name_d).statistic),
                        rho_ir_syntax=float(stats.spearmanr(s_.e_ir_d, s_.e_op_d).statistic),
                        e_ir_median=float(s_.e_ir_d.median()), e_tok_median=float(s_.e_tok_d.median()))
# binned relation for a chart: deciles of compiled energy, median text energy, per group
bins = np.quantile(DJ.e_ir_d, np.linspace(0, 1, 11))
DJ['bin'] = np.clip(np.searchsorted(bins, DJ.e_ir_d, side='right') - 1, 0, 9)
binned = DJ.groupby(['group', 'bin']).agg(e_ir=('e_ir_d', 'median'), e_tok=('e_tok_d', 'median'), n=('name', 'size')).reset_index()

# gesture over/under-representation (project-balanced shares)
lr = []
for g in vocab:
    a, b = share['openai'][g], share['mathlib'][g]
    h = share['human'][g]
    lr.append(dict(gesture=g, desc=describe(g), openai=a, mathlib=b, human=h,
                   log2_ratio=math.log2((a + 1e-5) / (b + 1e-5))))
LR = pd.DataFrame(lr).sort_values('log2_ratio')

res = dict(
    sizes=D.groupby('group').agg(theorems=('name', 'size'), projects=('project', 'nunique')).reset_index().to_dict('records'),
    n_projects=P.groupby('group').size().to_dict(),
    groups=group_rows, tests=T.to_dict('records'), text_vs_ir=tvc,
    kl_bits=dict(openai=float(contrib.sum()), human=float(contribH.sum()),
                 openai_top8_share=float(contrib[:8].sum() / contrib.sum()),
                 human_top8_share=float(contribH[:8].sum() / contribH.sum())),
    spectrum=dict(openai=[dict(rank=k + 1, lam=float(lam[k]), shift=float(delta[k]), bits=float(contrib[k])) for k in range(40)],
                  human=[dict(rank=k + 1, lam=float(lamH[k]), shift=float(deltaH[k]), bits=float(contribH[k])) for k in range(40)]),
    modes=modes, stability=stability, normal_modes=normal,
    over=LR.tail(12).iloc[::-1].to_dict('records'), under=LR.head(12).to_dict('records'),
    vocab_size=K, n_decls_eigen=int(len(idx)),
    null=null_summary, null_human=null_human, sensitivity=sens, old_corr=old_corr, decl_join=decl_join,
    binned=binned.to_dict('records'), regularization=dict(alpha=ALPHA, floor=FLOOR),
)
json.dump(res, open(os.path.join(RES, 'results.json'), 'w'), indent=1, default=float, ensure_ascii=False)
pd.set_option('display.width', 220)
G = pd.DataFrame(group_rows)
print(G.pivot(index='label', columns='group', values='median').round(3))
print(T[['vs', 'label', 'diff', 'lo', 'hi', 'auc', 'q']].round(3).to_string())
print('text vs IR', tvc)
print('KL bits openai', contrib.sum(), 'human', contribH.sum())
for md in modes:
    print(md['rank'], round(md['lam'], 2), round(md['shift'], 2), round(md['bits'], 3), [p['gesture'] for p in md['pos'][:5]])
print('stability', np.round(stability, 2))
print('null', null_summary)
print('sensitivity', [(x['alpha'], round(x['total'], 1), [round(t, 2) for t in x['match_to_main'][:6]]) for x in sens])
print('decl join', decl_join)
