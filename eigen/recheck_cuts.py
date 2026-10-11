"""Re-run the earlier analyses in light of the cut findings.

Joins each theorem's cut measures (cuts_exact.proof_measures) to analysis_merged/decls.pkl and writes
subset analysis directories for stats_eigen.py:
  analysis_rho0  - theorems already in optimal cut layout (rho = 0: written = profitable-cuts-only form)
  analysis_nocut - theorems with no cut at all
Also writes analysis_merged/cutjoin.pkl (per-theorem rho, chi, kappa, ncuts, k1).
"""
import os, pickle, sys
import numpy as np, pandas as pd
os.environ.setdefault('WITH_AI', '0')
from cuts_exact import load, proof_measures

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'out_final', 'analysis_merged')
rows = []
for corpus, projs in load().items():
    if corpus not in ('mathlib', 'openai', 'human'):
        continue
    for proj, recs in projs.items():
        for n, t in recs.items():
            m = proof_measures(t)
            rows.append(dict(group=corpus, name=n, rho=m['rho'], chi=m['chi'], kappa=m['kappa'],
                             ncuts=m['cuts'], k1=m['k1'], N0=m['N0'], N4=m['N4']))
C = pd.DataFrame(rows).drop_duplicates(['group', 'name'])
D = pd.read_pickle(os.path.join(BASE, 'decls.pkl'))
J = D[['group', 'name']].reset_index().merge(C, on=['group', 'name'], how='left').set_index('index').loc[D.index]
J.to_pickle(os.path.join(BASE, 'cutjoin.pkl'))
print('joined share by group:', J.groupby('group').rho.apply(lambda s: s.notna().mean()).round(3).to_dict())
blob = pickle.load(open(os.path.join(BASE, 'unigrams.pkl'), 'rb'))
for name, mask in [('analysis_rho0', J.N0.eq(J.N4) | (J.rho.abs() < 1e-12)), ('analysis_nocut', J.ncuts.eq(0))]:
    mask = mask.fillna(False).to_numpy()
    out = os.path.join(HERE, 'out_final', name)
    os.makedirs(out, exist_ok=True)
    pos = np.flatnonzero(mask)
    D.iloc[pos].reset_index(drop=True).to_pickle(os.path.join(out, 'decls.pkl'))
    pickle.dump({k: [v[i] for i in pos] for k, v in blob.items()}, open(os.path.join(out, 'unigrams.pkl'), 'wb'))
    print(name, 'kept share by group:', pd.Series(mask, index=D.index).groupby(D.group).mean().round(3).to_dict())
