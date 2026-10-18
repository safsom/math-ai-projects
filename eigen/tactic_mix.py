"""Do the corpus differences survive a control for tactic mix?

For each proof: its share of automation-certificate gestures (tac:*), its share of rewriting glue, and its size. Each
measure is compared with what mathlib proofs of the same mix and size show (the mean in the same cell of mathlib),
and the projects are then compared on the residuals, as in the paper (project means, Mann-Whitney AUC).

Reads out_final/analysis_merged (decls.pkl, cutjoin.pkl) and out_final/analysis_author (author steps).
Writes out_final/tactic_mix.json.
"""
import json, os, pickle
import numpy as np, pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'out_final', 'analysis_merged')
MIN_NODES, MIN_PROOFS = 10, 20

D = pd.read_pickle(os.path.join(BASE, 'decls.pkl'))
J = pd.read_pickle(os.path.join(BASE, 'cutjoin.pkl'))
A = pd.read_pickle(os.path.join(HERE, 'out_final', 'analysis_author', 'decls.pkl'))
UA = pickle.load(open(os.path.join(HERE, 'out_final', 'analysis_author', 'unigrams.pkl'), 'rb'))['U']
author = pd.Series([sum(u.values()) for u in UA], index=pd.MultiIndex.from_arrays([A.group, A.name]))

hyp = D[['hyp_0', 'hyp_1', 'hyp_ω']].sum(1)
cut = D[['cut_0', 'cut_1', 'cut_ω']].sum(1)
X = pd.DataFrame({
    'group': D.group, 'project': D.project, 'nodes': D.nodes,
    'auto': D['fam:automation certificate'] / D.nodes,
    'rw': D['fam:rewrite along an equation'] / D.nodes,
    'steps': D.nodes.astype(float),
    'author_steps': author.reindex(pd.MultiIndex.from_arrays([D.group, D.name])).to_numpy(),
    'unused_hyp': D.hyp_0 / hyp.replace(0, np.nan),
    'claims_per_100': 100 * cut / D.nodes,
    'unused_claims': D.cut_0 / cut.replace(0, np.nan),
    'e_ir': D.E_ir / D.steps,
    'rho': J.rho.to_numpy(), 'chi': J.chi.to_numpy(), 'kappa': J.kappa.to_numpy(),
})
X = X[(X.nodes >= MIN_NODES) & X.group.isin(['mathlib', 'openai', 'human'])].copy()
n_proj = X.groupby(['group', 'project']).size()
X = X.set_index(['group', 'project']).loc[n_proj[n_proj >= MIN_PROOFS].index].reset_index()

# cells: automation share, rewriting share, size
X['a_bin'] = pd.cut(X.auto, [-1, 0, 0.05, 0.15, 0.3, 0.5, 1.01], labels=False)
X['r_bin'] = pd.cut(X.rw, [-1, 0, 0.05, 0.15, 0.3, 1.01], labels=False)
X['s_bin'] = pd.qcut(np.log(X.nodes), 8, labels=False, duplicates='drop')
SIZE = ('steps', 'author_steps')  # size is the outcome here: control for mix only
OUTCOMES = ['steps', 'author_steps', 'unused_hyp', 'claims_per_100', 'unused_claims', 'e_ir', 'rho', 'chi', 'kappa']


def auc(a, b):
    a, b = np.asarray(a), np.asarray(b)
    U, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    return float(U / (len(a) * len(b))), float(p)


def expected(y, cells):
    """Mathlib's mean of y in each proof's cell (NaN where mathlib has fewer than 20 proofs in the cell)."""
    M = X.group.eq('mathlib') & y.notna()
    g = y[M].groupby([X.loc[M, c] for c in cells])
    mu = g.mean()[g.size() >= 20]
    key = pd.MultiIndex.from_frame(X[cells])
    return pd.Series(mu.reindex(key).to_numpy(), index=X.index)


res = dict(mix={}, outcomes={})
for g in ('mathlib', 'openai', 'human'):
    P = X[X.group == g].groupby('project')[['auto', 'rw']].mean()
    res['mix'][g] = dict(projects=len(P), auto_median=float(P.auto.median()), rw_median=float(P.rw.median()),
                         proofs_with_auto=float((X[X.group == g].auto > 0).mean()))
res['mix']['auc_openai_vs_mathlib'] = {k: auc(X[X.group == 'openai'].groupby('project')[k].mean(),
                                              X[X.group == 'mathlib'].groupby('project')[k].mean())[0] for k in ('auto', 'rw')}
for y in OUTCOMES:
    v = X[y].astype(float)
    if y in ('steps', 'author_steps'):
        v = np.log(v.where(v > 0))
    cells = ['a_bin', 'r_bin'] if y in SIZE else ['a_bin', 'r_bin', 's_bin']
    e = expected(v, cells)
    row = dict(covered=float(e[v.notna()].notna().mean()))
    for lab, s in (('raw', v), ('adjusted', v - e)):
        P = s.groupby([X.group, X.project]).mean().dropna()
        for o in ('openai', 'human'):
            a, p = auc(P[o], P['mathlib'])
            row[f'{lab}_auc_{o}'], row[f'{lab}_p_{o}'] = a, p
        row[f'{lab}_median'] = {g: float(P[g].median()) for g in ('mathlib', 'openai', 'human')}
    # proofs with no automation at all, no adjustment
    Z = X.auto.eq(0)
    P = v[Z].groupby([X.group[Z], X.project[Z]]).mean().dropna()
    P = P[(Z.groupby([X.group, X.project]).sum() >= MIN_PROOFS).reindex(P.index).fillna(False)]
    row['noauto_auc_openai'], row['noauto_p_openai'] = auc(P['openai'], P['mathlib'])
    row['noauto_projects_openai'] = int(len(P['openai']))
    row['noauto_median'] = {g: float(P[g].median()) for g in ('mathlib', 'openai')}
    row['noauto_auc_human'] = auc(P['human'], P['mathlib'])[0] if 'human' in P.index.get_level_values(0) else None
    res['outcomes'][y] = row

json.dump(res, open(os.path.join(HERE, 'out_final', 'tactic_mix.json'), 'w'), indent=1)
print(json.dumps(res['mix'], indent=1))
T = pd.DataFrame({y: {k: r[k] for k in ('covered', 'raw_auc_openai', 'adjusted_auc_openai', 'noauto_auc_openai',
                                        'raw_auc_human', 'adjusted_auc_human', 'noauto_auc_human')}
                  for y, r in res['outcomes'].items()}).T
print(T.round(2).to_string())
