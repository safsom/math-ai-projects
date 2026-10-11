"""OpenAI's eigenproofs (main basis, analysis_merged) scored separately on theorems with and without
redundant cut layout (rho > 0 vs rho = 0). Writes out_final/analysis_merged/recheck_ep.json."""
import collections, json, math, os, pickle
import numpy as np, pandas as pd
from scipy import linalg, stats
RES = 'out_final/analysis_merged'
K, MIN_NODES, ALPHA, FLOOR = 300, 10, 0.1, 0.01
D = pd.read_pickle(f'{RES}/decls.pkl'); U = pickle.load(open(f'{RES}/unigrams.pkl', 'rb'))['U']
J = pd.read_pickle(f'{RES}/cutjoin.pkl')
grp, proj = D.group.to_numpy(), D.project.to_numpy()
idx = np.flatnonzero((D.nodes >= MIN_NODES).to_numpy() & D.group.isin(['mathlib', 'openai', 'human']).to_numpy())
gi = grp[idx]
def bw(ix):
    w = np.zeros(len(ix))
    for g in set(grp[ix]):
        m = grp[ix] == g; c = collections.Counter(proj[ix][m])
        w[m] = [1.0 / c[p] for p in proj[ix][m]]; w[m] /= w[m].sum()
    return w
W0 = bw(idx)
share = collections.defaultdict(collections.Counter)
for j, i in enumerate(idx):
    if gi[j] in ('mathlib', 'openai'):
        t = sum(U[i].values())
        for g, c in U[i].items(): share[gi[j]][g] += W0[j] * c / t
sc = collections.Counter({g: share['mathlib'][g] + share['openai'][g] for g in set(share['mathlib']) | set(share['openai'])})
vocab = [g for g, _ in sc.most_common(K)]; vix = {g: k for k, g in enumerate(vocab)}
X = np.zeros((len(idx), K + 1))
for j, i in enumerate(idx):
    t = sum(U[i].values())
    for g, c in U[i].items(): X[j, vix.get(g, K)] += c / t
X = np.sqrt(X)
def mom(Xs, w):
    mu = w @ Xs; Z = Xs - mu; return mu, (Z * w[:, None]).T @ Z
def reg(S):
    d = np.diag(S); return (1 - ALPHA) * S + ALPHA * np.diag(d) + FLOOR * max(d.mean(), 1e-4) * np.eye(len(d))
def eig(a, b):
    lam, Wv = linalg.eigh(reg(a[1]), reg(b[1])); dl = Wv.T @ (a[0] - b[0])
    c = 0.5 * (lam - 1 - np.log(lam) + dl ** 2) / math.log(2); o = np.argsort(-c)
    return lam[o], Wv[:, o], dl[o], c[o]
mats = {g: mom(X[gi == g], W0[gi == g] / W0[gi == g].sum()) for g in ('mathlib', 'openai', 'human')}
lam, Wv, dl, con = eig(mats['openai'], mats['mathlib'])
print('check: KL', round(con.sum(), 2), 'EP1 bits', round(con[0], 2))
rho = J.rho.to_numpy()[idx]; k1 = J.k1.to_numpy()[idx]
layout = np.where(np.isnan(rho), 'nojoin', np.where(np.abs(rho) < 1e-12, 'rho0', 'rho+'))
out = dict(kl=float(con.sum()), modes=[])
muM = mats['mathlib'][0]
for k in range(8):
    w = Wv[:, k] * (1 if dl[k] >= 0 else -1); s = (X - muM) @ w
    row = dict(ep=k + 1, bits=float(con[k]))
    for g in ('openai', 'mathlib', 'human'):
        for L in ('rho0', 'rho+'):
            m = (gi == g) & (layout == L)
            ww = W0[m] / W0[m].sum()
            row[f'{g}_{L}'] = dict(share=float(W0[gi == g][layout[gi == g] == L].sum() / W0[gi == g].sum()),
                                   mean=float(ww @ s[m]), beyond2=float(ww @ (s[m] > 2)))
        m = (gi == g) & ~np.isnan(rho)
        row[f'{g}_spearman_rho'] = float(stats.spearmanr(s[m], rho[m])[0])
    # share of OpenAI's (project-balanced) excess beyond +2 carried by rho>0 theorems
    m = gi == 'openai'; ww = W0[m] / W0[m].sum(); ex = ww * (s[m] > 2)
    row['openai_excess_from_rho+'] = float(ex[layout[m] == 'rho+'].sum() / ex.sum())
    out['modes'].append(row)
# KL of OpenAI vs mathlib in the fixed basis, each layout stratum against mathlib's rho=0 theorems
for L in ('rho0', 'rho+'):
    m = (gi == 'openai') & (layout == L)
    mm = (gi == 'mathlib') & (layout == L)
    a = mom(X[m], W0[m] / W0[m].sum()); b = mom(X[mm], W0[mm] / W0[mm].sum())
    out[f'kl_{L}_vs_mathlib_{L}'] = float(eig(a, b)[3].sum())
json.dump(out, open(f'{RES}/recheck_ep.json', 'w'), indent=1)
for r in out['modes']:
    print(r['ep'], round(r['bits'], 1), 'OAI beyond2 rho0/rho+', round(r['openai_rho0']['beyond2'], 3), round(r['openai_rho+']['beyond2'], 3),
          'ML', round(r['mathlib_rho0']['beyond2'], 3), round(r['mathlib_rho+']['beyond2'], 3),
          'excess from rho+', round(r['openai_excess_from_rho+'], 2), 'spearman', round(r['openai_spearman_rho'], 2))
print('OAI share rho+', round(out['modes'][0]['openai_rho+']['share'], 3), {k: round(v, 1) for k, v in out.items() if k.startswith('kl')})
