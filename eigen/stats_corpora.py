"""The compiled statistics of stats_eigen.py, for every corpus at once.

Reads decls.pkl / unigrams.pkl from an analyze.py run with WITH_AI=1. The eigenproof basis is OpenAI's
(rebuilt exactly as in stats_eigen.py: same vocabulary, weights and regularization); every corpus is
scored on it, and each corpus also gets its own divergence from mathlib against a size-matched null.
Writes <RES>/corpora.json.
"""
import collections, json, math, os, pickle, sys
import numpy as np
import pandas as pd
from scipy import linalg, stats

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.environ.get('GOUT', os.path.join(HERE, 'out_final')), os.environ.get('RESNAME', 'analysis_all'))
K, MIN_NODES, MIN_THM, B = 300, 10, 20, 2000
ALPHA, FLOOR = 0.1, 0.01
rng = np.random.default_rng(20261010)
sys.path.insert(0, HERE)
from gloss import describe  # noqa: E402

D = pd.read_pickle(os.path.join(RES, 'decls.pkl'))
U = pickle.load(open(os.path.join(RES, 'unigrams.pkl'), 'rb'))['U']
CORPORA = [g for g in ['openai', 'human', 'flt', 'spherepacking', 'erdos90', 'putnam2025', 'imo2025'] if (D.group == g).any()]

# ------------------------------------------------------------------ project table (as stats_eigen.py)
agg = {'name': 'size', 'E_ir': 'sum', 'steps': 'sum', 'nodes': ['sum', 'median'],
       **{f'hyp_{m}': 'sum' for m in '01ω'}, **{f'cut_{m}': 'sum' for m in '01ω'}}
P = D.groupby(['group', 'project']).agg(agg)
P.columns = ['n', 'E', 'steps', 'nodes', 'nodes_med'] + [f'hyp_{m}' for m in '01ω'] + [f'cut_{m}' for m in '01ω']
P = P.reset_index()
P['e_ir'] = P.E / P.steps
hyp = P[[f'hyp_{m}' for m in '01ω']].sum(1)
cut = P[[f'cut_{m}' for m in '01ω']].sum(1)
P['weakening'] = P.hyp_0 / hyp
P['contraction'] = P['hyp_ω'] / hyp
P['cuts_per_100'] = 100 * cut / P.nodes
P['single_use_cut'] = P.cut_1 / cut.replace(0, np.nan)
P = P[P.n >= MIN_THM].copy()
METRICS = ['e_ir', 'nodes_med', 'weakening', 'contraction', 'cuts_per_100', 'single_use_cut']


def auc_test(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3:
        return None
    u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    return dict(auc=float(u / (len(a) * len(b))), p=float(p), n=len(a))


# per-theorem compiled energy (bits per step), theorems with >= MIN_NODES steps
D['e_thm'] = D.E_ir / D.steps.replace(0, np.nan)
big = D[D.nodes >= MIN_NODES]

# ------------------------------------------------------------------ gesture vectors (as stats_eigen.py)
grp, proj = D.group.to_numpy(), D.project.to_numpy()
idx = np.flatnonzero((D.nodes >= MIN_NODES).to_numpy() & D.group.isin(['mathlib'] + CORPORA).to_numpy())
gi = grp[idx]


def balanced_weights(ix):
    w = np.zeros(len(ix))
    for g in set(grp[ix]):
        m = grp[ix] == g
        counts = collections.Counter(proj[ix][m])
        w[m] = [1.0 / counts[p] for p in proj[ix][m]]
        w[m] /= w[m].sum()
    return w


W0 = balanced_weights(idx)
share = collections.defaultdict(collections.Counter)
for j, i in enumerate(idx):
    if gi[j] in ('mathlib', 'openai'):
        tot = sum(U[i].values())
        for g, c in U[i].items():
            share[gi[j]][g] += W0[j] * c / tot
score = collections.Counter({g: share['mathlib'][g] + share['openai'][g] for g in set(share['mathlib']) | set(share['openai'])})
vocab = [g for g, _ in score.most_common(K)]
vix = {g: k for k, g in enumerate(vocab)}
names_all = vocab + ['(other gestures)']
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


def regularize(S, alpha=ALPHA, floor=FLOOR):
    d = np.diag(S)
    return (1 - alpha) * S + alpha * np.diag(d) + floor * max(d.mean(), 1e-4) * np.eye(len(d))


def gen_eig(mu_o, S_o, mu_m, S_m):
    lam, Wv = linalg.eigh(regularize(S_o), regularize(S_m))
    delta = Wv.T @ (mu_o - mu_m)
    contrib = 0.5 * (lam - 1 - np.log(lam) + delta ** 2) / math.log(2)
    order = np.argsort(-contrib)
    return lam[order], Wv[:, order], delta[order], contrib[order]


mats = {}
for g in ['mathlib'] + CORPORA:
    m = gi == g
    mats[g] = wmoments(X[m], W0[m] / W0[m].sum())
muM, SM = mats['mathlib']
SMr = regularize(SM)
lam, Wv, delta, contrib = gen_eig(*mats['openai'], muM, SM)
mathlib_projects = sorted(set(proj[idx][gi == 'mathlib']))


def null_for(n_proj, reps=10):
    tot = []
    for _ in range(reps):
        perm = rng.permutation(len(mathlib_projects))
        A = {mathlib_projects[t] for t in perm[:n_proj]}
        inA = np.isin(proj[idx], list(A))
        mA, mB = (gi == 'mathlib') & inA, (gi == 'mathlib') & ~inA
        wA, wB = balanced_weights(idx[mA]), balanced_weights(idx[mB])
        c0 = gen_eig(*wmoments(X[mA], wA / wA.sum()), *wmoments(X[mB], wB / wB.sum()))[3]
        tot.append(float(c0.sum()))
    return dict(median=float(np.median(tot)), max=float(np.max(tot)))


def pattern(w):
    p = SMr @ w
    return p / np.linalg.norm(p)


out = dict(corpora={}, eigenproof_prevalence={}, own_direction={}, tests={})
for g in CORPORA:
    m = gi == g
    npj = len(set(proj[idx][m]))
    lam_g, W_g, d_g, c_g = gen_eig(*mats[g], muM, SM)
    nul = null_for(max(3, npj))
    sub = P[P.group == g]
    out['corpora'][g] = dict(
        projects=int(npj), projects_ge20=int(len(sub)), theorems=int((D.group == g).sum()),
        theorems_ge10=int(m.sum()), kl_bits=float(c_g.sum()), null_median=nul['median'], null_max=nul['max'],
        ratio=float(c_g.sum() / nul['median']),
        e_thm_median=float(big.loc[big.group == g, 'e_thm'].median()),
        nodes_median=float(big.loc[big.group == g, 'nodes'].median()),
        project_medians={k: float(sub[k].median()) if len(sub) else None for k in METRICS})
    # OpenAI's eigenproofs: how often this corpus's theorems score beyond +2 mathlib SD
    prev = []
    for k in range(8):
        w = Wv[:, k] * (1 if delta[k] >= 0 else -1)
        sc = (X[m] - muM) @ w
        ww = W0[m] / W0[m].sum()
        prev.append(dict(ep=k + 1, mean=float(ww @ sc), beyond2=float(ww @ (sc > 2))))
    out['eigenproof_prevalence'][g] = prev
    # the corpus's own most divergent direction
    w = W_g[:, 0] * (1 if d_g[0] >= 0 else -1)
    pt = pattern(w)
    top = np.argsort(-pt)[:6]
    cos_ep = [float(abs(pt @ pattern(Wv[:, k]))) for k in range(8)]
    out['own_direction'][g] = dict(bits=float(c_g[0]), shift=float(abs(d_g[0])), lam=float(lam_g[0]),
                                   top=[dict(gesture=names_all[t], desc=describe(names_all[t]), loading=float(pt[t])) for t in top],
                                   match_openai_ep=cos_ep)
    out['tests'][g] = {ref: {k: auc_test(sub[k], P.loc[P.group == ref, k]) for k in METRICS}
                       for ref in ('mathlib', 'human') if ref != g}
out['mathlib'] = dict(projects=len(mathlib_projects), e_thm_median=float(big.loc[big.group == 'mathlib', 'e_thm'].median()),
                      nodes_median=float(big.loc[big.group == 'mathlib', 'nodes'].median()),
                      project_medians={k: float(P.loc[P.group == 'mathlib', k].median()) for k in METRICS})
json.dump(out, open(os.path.join(RES, 'corpora.json'), 'w'), indent=1)
print(pd.DataFrame(out['corpora']).T[['projects', 'theorems', 'kl_bits', 'null_median', 'ratio', 'e_thm_median']].round(2))
print(pd.DataFrame({g: [p['beyond2'] for p in v] for g, v in out['eigenproof_prevalence'].items()},
                   index=[f'EP{k}' for k in range(1, 9)]).round(3))
for g, v in out['own_direction'].items():
    print(g, round(v['bits'], 1), [t['gesture'] for t in v['top'][:4]], 'best EP match', round(max(v['match_openai_ep']), 2))
