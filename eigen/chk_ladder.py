"""Rank-ladder check on a proof-term output: every created proof redex needs a cut of rank >= 1."""
import json, sys
import numpy as np

R = [json.loads(l) for l in open(sys.argv[1])]
R = [r for r in R if 'tS' in r and not r.get('tt')]


def maxr(h):
    h = np.array(h).reshape(4, 3)
    return max((i for i in range(4) if h[i].sum()), default=-1)


print('proofs', len(R))
for key in ('rk', 'rku'):
    for lab in ('tResid', 'tResidP'):
        S = [r for r in R if r.get(lab, 0) > 0]
        print(key, lab, len(S), 'with a rank>=1 cut:', round(float(np.mean([maxr(r[key]) >= 1 for r in S])), 4) if S else None)
for key in ('rk', 'rku'):
    print(key, '\n', np.array([r[key] for r in R]).sum(0).reshape(4, 3))
bad = [r['n'] for r in R if r.get('tResidP', 0) > 0 and maxr(r['rku']) < 1]
print('violations', len(bad), bad[:10])
